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

pub fn spawn_sidecar(_app: &AppHandle) -> Result<Child, String> {
    // Resolve dev engine directory from environment variable or fallback to ../../engine relative path
    let engine_dir = if let Ok(val) = env::var("CORPUSSIEVE_ENGINE_DIR") {
        PathBuf::from(val)
    } else {
        PathBuf::from("../../engine")
    };

    let cwd = if engine_dir.exists() {
        engine_dir.canonicalize().unwrap_or(engine_dir)
    } else {
        env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
    };

    // Dev mode execution via python/uv
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
        if let Ok(c) = spawn_sidecar(&app) {
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
