// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine;

use engine::{engine_call, engine_status, EngineState};

fn main() {
    tauri::Builder::default()
        .manage(EngineState::default())
        .invoke_handler(tauri::generate_handler![engine_call, engine_status])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
