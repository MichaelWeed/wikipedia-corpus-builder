use std::env;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

pub struct EngineState {
    pub child: Mutex<Option<Child>>,
    pub restart_count: Mutex<u32>,
}

impl Default for EngineState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            restart_count: Mutex::new(0),
        }
    }
}

// Name Tauri's bundler copies the PyInstaller sidecar to, alongside the main
// app executable (Contents/MacOS/ on macOS, next to the .exe on Windows/
// Linux) -- verified empirically via `tauri build --debug` and inspecting
// the resulting bundle. `externalBin` binaries are built per-platform by
// engine/scripts/build_sidecar.sh under the target-triple-suffixed name
// Tauri's convention requires (see tauri.conf.json's bundle.externalBin);
// the bundler strips that suffix when it copies the file into the bundle,
// since the bundle itself is already platform-specific.
fn bundled_sidecar_name() -> &'static str {
    if cfg!(windows) {
        "corpussieve-engine.exe"
    } else {
        "corpussieve-engine"
    }
}

/// Path to a bundled sidecar binary next to the running executable, if one
/// is actually there. This -- not a debug/release build-flavor check -- is
/// the real signal for "packaged app" vs "dev mode": `tauri build --debug`
/// (used by CI to test bundling) still has debug_assertions on, but does
/// have the sidecar bundled; `cargo run`/`tauri dev` never do.
fn bundled_sidecar_path() -> Option<PathBuf> {
    let exe = env::current_exe().ok()?;
    let dir = exe.parent()?;
    let candidate = dir.join(bundled_sidecar_name());
    candidate.is_file().then_some(candidate)
}

pub fn spawn_sidecar() -> Result<Child, String> {
    if let Some(sidecar_path) = bundled_sidecar_path() {
        return Command::new(&sidecar_path)
            .args(["engine", "serve"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn bundled engine sidecar at {:?}: {}", sidecar_path, e));
    }

    // Dev-mode fallback: no bundled sidecar next to this executable, so this
    // is `cargo run`/`tauri dev` from the source tree -- shell out to `uv
    // run` against the engine directory instead. `CORPUSSIEVE_ENGINE_DIR`
    // allows an explicit override (e.g. for CI or non-standard checkouts);
    // otherwise the path is anchored to this crate's location at compile
    // time (CARGO_MANIFEST_DIR), not the process's runtime CWD, since
    // Tauri's dev/launch CWD is not guaranteed.
    let engine_dir = if let Ok(val) = env::var("CORPUSSIEVE_ENGINE_DIR") {
        PathBuf::from(val)
    } else {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../engine")
    };

    let cwd = engine_dir
        .canonicalize()
        .map_err(|e| format!("Engine directory not found at {:?}: {}", engine_dir, e))?;

    let child = Command::new("uv")
        .args(["run", "corpussieve", "engine", "serve"])
        .current_dir(cwd)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("Failed to spawn engine sidecar: {}", e))?;

    Ok(child)
}

#[tauri::command]
pub async fn engine_status(state: State<'_, EngineState>) -> Result<serde_json::Value, String> {
    let mut lock = state.child.lock().map_err(|e| e.to_string())?;
    let restarts = *state.restart_count.lock().map_err(|e| e.to_string())?;

    let is_alive = if let Some(ref mut child) = *lock {
        matches!(child.try_wait(), Ok(None))
    } else {
        false
    };

    Ok(serde_json::json!({
        "alive": is_alive,
        "restart_count": restarts,
    }))
}

#[tauri::command]
pub async fn engine_call(
    method: String,
    params: serde_json::Value,
    state: State<'_, EngineState>,
    app: AppHandle,
) -> Result<serde_json::Value, String> {
    let request_id = rand::random::<u32>();
    let req = serde_json::json!({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    });

    let req_str = format!("{}\n", serde_json::to_string(&req).unwrap());

    let mut lock = state.child.lock().map_err(|e| e.to_string())?;
    let mut restarts = state.restart_count.lock().map_err(|e| e.to_string())?;

    // Check if process has crashed or is not running
    let needs_spawn = match *lock {
        None => true,
        Some(ref mut child) => match child.try_wait() {
            Ok(Some(_status)) => {
                *restarts += 1;
                true
            }
            Ok(None) => false,
            Err(_) => true,
        },
    };

    if needs_spawn {
        if *restarts > 3 {
            return Err("Engine sidecar crashed maximum allowed times (3). Restart desktop app.".into());
        }
        if let Ok(c) = spawn_sidecar() {
            *lock = Some(c);
        } else {
            return Err("Failed to spawn engine sidecar process.".into());
        }
    }

    if let Some(ref mut child) = *lock {
        if let Some(ref mut stdin) = child.stdin {
            stdin
                .write_all(req_str.as_bytes())
                .map_err(|e| format!("Failed write to engine: {}", e))?;
            stdin.flush().map_err(|e| e.to_string())?;
        }

        if let Some(ref mut stdout) = child.stdout {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            while reader.read_line(&mut line).is_ok() {
                if line.trim().is_empty() {
                    line.clear();
                    continue;
                }
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) {
                    if v.get("method").is_some() && v.get("id").is_none() {
                        // Event notification from engine
                        let _ = app.emit("engine-event", &v);
                        line.clear();
                        continue;
                    }
                    if v.get("id") == Some(&serde_json::json!(request_id)) {
                        if let Some(err) = v.get("error") {
                            return Err(serde_json::to_string(err).unwrap());
                        }
                        return Ok(v.get("result").cloned().unwrap_or(serde_json::Value::Null));
                    }
                }
                line.clear();
            }
        }
    }

    Err("Engine sidecar unreachable".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Proves the actual packaged-app code path end to end: copy the real
    /// PyInstaller sidecar (built by engine/scripts/build_sidecar.sh) next
    /// to this test binary -- exactly where Tauri's bundler places it next
    /// to the app executable in a real .app, verified empirically via
    /// `tauri build --debug` -- then call the same spawn_sidecar() used in
    /// production and do a real engine.hello round trip over its stdio.
    /// Skips (doesn't fail) if the sidecar hasn't been built, since it's a
    /// separate, optional build step (`engine/scripts/build_sidecar.sh`),
    /// not part of a plain `cargo test`.
    #[test]
    fn spawns_bundled_sidecar_and_completes_a_real_rpc_round_trip() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let binaries_dir = manifest_dir.join("binaries");
        let Some(source) = std::fs::read_dir(&binaries_dir).ok().and_then(|entries| {
            entries
                .filter_map(|e| e.ok())
                .map(|e| e.path())
                .find(|p| p.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with("corpussieve-engine-")))
        }) else {
            eprintln!(
                "skipping: no sidecar binary in {:?} -- run engine/scripts/build_sidecar.sh first",
                binaries_dir
            );
            return;
        };

        let exe = env::current_exe().expect("current_exe");
        let dest = exe.parent().expect("parent dir").join(bundled_sidecar_name());

        // Detection must not false-positive before the binary is actually
        // there (both assertions live in this one test, not a separate
        // test function, since `bundled_sidecar_path()`'s target directory
        // is shared process-wide -- a second test toggling the same file
        // concurrently would race Rust's default parallel test runner).
        assert!(bundled_sidecar_path().is_none());

        std::fs::copy(&source, &dest).expect("copy sidecar next to test binary");
        assert_eq!(bundled_sidecar_path().as_deref(), Some(dest.as_path()));

        let cleanup = || {
            let _ = std::fs::remove_file(&dest);
        };

        let result = (|| -> Result<(), String> {
            let mut child = spawn_sidecar()?;
            let mut stdin = child.stdin.take().ok_or("no stdin")?;
            let stdout = child.stdout.take().ok_or("no stdout")?;

            stdin
                .write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"engine.hello\",\"params\":{}}\n")
                .map_err(|e| e.to_string())?;
            stdin.flush().map_err(|e| e.to_string())?;

            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            reader.read_line(&mut line).map_err(|e| e.to_string())?;

            let v: serde_json::Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
            if v.get("result").and_then(|r| r.get("protocol_version")).and_then(|p| p.as_i64()) != Some(1) {
                return Err(format!("unexpected response: {line}"));
            }

            let _ = child.kill();
            let _ = child.wait();
            Ok(())
        })();

        cleanup();
        assert!(bundled_sidecar_path().is_none(), "cleanup must remove the copied sidecar");
        result.expect("bundled sidecar round trip");
    }
}
