use serde::Serialize;
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandEvent, CommandChild};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use windows::Win32::Foundation::HWND;
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowLongW, SetWindowLongW, ShowWindow, GWL_EXSTYLE, SW_SHOWNA, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
};
use windows::Media::Control::GlobalSystemMediaTransportControlsSessionManager;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use rodio::{Decoder, OutputStream, Source, OutputStreamHandle};
use std::io::Cursor;

#[derive(Debug, Clone, Serialize, Copy)]
#[serde(rename_all = "lowercase")]
pub enum OrbState {
    Idle,
    Listening,
    Recording,
    Processing,
    Success,
    Error,
}

struct SendSyncWrapper<T>(T);
unsafe impl<T> Send for SendSyncWrapper<T> {}
unsafe impl<T> Sync for SendSyncWrapper<T> {}

struct AppState {
    pub state: Mutex<OrbState>,
    pub python_child: Mutex<Option<CommandChild>>,
    pub audio_handle: OutputStreamHandle,
    _audio_stream: SendSyncWrapper<OutputStream>,
}

const WAKE_MP3: &[u8] = include_bytes!("../assets/wake.mp3");
const SUCCESS_MP3: &[u8] = include_bytes!("../assets/success.mp3");
const ERROR_MP3: &[u8] = include_bytes!("../assets/error.mp3");

fn play_sound(handle: &OutputStreamHandle, data: &'static [u8]) {
    let cursor = Cursor::new(data);
    if let Ok(source) = Decoder::new(cursor) {
        let _ = handle.play_raw(source.convert_samples());
    }
}

fn play_wake_sound(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    play_sound(&state.audio_handle, WAKE_MP3);
}

fn play_success_sound(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    play_sound(&state.audio_handle, SUCCESS_MP3);
}

fn play_error_sound(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    play_sound(&state.audio_handle, ERROR_MP3);
}

#[tauri::command]
async fn toggle_playback() -> Result<(), String> {
    let manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync()
        .map_err(|e| e.to_string())?.await
        .map_err(|e| e.to_string())?;
    
    if let Ok(session) = manager.GetCurrentSession() {
        let _ = session.TryTogglePlayPauseAsync().map_err(|e| e.to_string())?.await;
    }
    Ok(())
}

#[tauri::command]
async fn media_command(command: String) -> Result<(), String> {
    let manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync()
        .map_err(|e| e.to_string())?.await
        .map_err(|e| e.to_string())?;
    
    if let Ok(session) = manager.GetCurrentSession() {
        match command.as_str() {
            "next" => { let _ = session.TrySkipNextAsync().map_err(|e| e.to_string())?.await; },
            "prev" => { let _ = session.TrySkipPreviousAsync().map_err(|e| e.to_string())?.await; },
            "play" => { let _ = session.TryPlayAsync().map_err(|e| e.to_string())?.await; },
            "pause" => { let _ = session.TryPauseAsync().map_err(|e| e.to_string())?.await; },
            _ => {}
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let ctrl_shift_j = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyJ);

    // Initialize audio output stream and handle
    let (audio_stream, audio_handle) = OutputStream::try_default().expect("Failed to initialize audio output");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |app, shortcut, event| {
                if shortcut == &ctrl_shift_j && event.state() == ShortcutState::Pressed {
                    let state = app.state::<AppState>();
                    let mut python_child_guard = state.python_child.lock().unwrap();
                    if let Some(child) = python_child_guard.as_mut() {
                        let _ = child.write(b"trigger\n");
                        println!("Manual trigger via hotkey sent to Python");
                    }
                }
            })
            .build()
        )
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            state: Mutex::new(OrbState::Idle),
            python_child: Mutex::new(None),
            audio_handle: audio_handle.clone(),
            _audio_stream: SendSyncWrapper(audio_stream),
        })
        .setup(move |app| {
            app.global_shortcut().register(ctrl_shift_j)?;

            let app_handle = app.handle().clone();
            
            // Setup System Tray
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&quit_i])?;
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| {
                    if event.id == "quit" {
                        // Explicitly kill the sidecar before exiting
                        let state = app.state::<AppState>();
                        let mut python_child_guard = state.python_child.lock().unwrap();
                        if let Some(child) = python_child_guard.take() {
                            let _ = child.kill();
                            println!("STT Sidecar killed on exit.");
                        }
                        app.exit(0);
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.set_ignore_cursor_events(false);
                        }
                    }
                })
                .build(app)?;

            // Initial window state: ignoring cursor events and positioned at bottom center
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_ignore_cursor_events(true);
                
                // Set WS_EX_NOACTIVATE to prevent focus and WS_EX_TOOLWINDOW to hide from Alt+Tab
                let hwnd = window.hwnd().unwrap();
                unsafe {
                    let style = GetWindowLongW(HWND(hwnd.0), GWL_EXSTYLE);
                    let _ = SetWindowLongW(HWND(hwnd.0), GWL_EXSTYLE, style | WS_EX_NOACTIVATE.0 as i32 | WS_EX_TOOLWINDOW.0 as i32);
                }

                // Position window at bottom center with 48px margin
                if let Ok(Some(monitor)) = window.current_monitor() {
                    let screen_size = monitor.size();
                    let scale_factor = monitor.scale_factor();
                    
                    // We use the outer_size which is already in physical pixels
                    if let Ok(win_size) = window.outer_size() {
                        let x = (screen_size.width as f64 - win_size.width as f64) / 2.0;
                        // 48 logical pixels converted to physical
                        let margin_bottom = 48.0 * scale_factor;
                        let y = screen_size.height as f64 - win_size.height as f64 - margin_bottom;
                        
                        let _ = window.set_position(tauri::PhysicalPosition::new(x, y));
                    }
                }
            }

            // Start the persistent STT sidecar with auto-restart logic
            tauri::async_runtime::spawn(async move {
                let shell = app_handle.shell();
                
                loop {
                    println!("Spawning STT sidecar...");
                    
                    // Use sidecar in production/build, or if the binary exists
                    // For dev without binary, this might fail unless we use .command("python")
                    // but we're moving towards a binary-first workflow.
                    let cmd = shell.sidecar("stt").unwrap_or_else(|_| {
                        // Fallback to python for dev if sidecar fails to load
                        shell.command("python").args(["-u", "stt.py"])
                    });

                    let (mut rx, child) = cmd.spawn()
                        .expect("Failed to spawn STT process");

                    // Store the child handle
                    {
                        let state = app_handle.state::<AppState>();
                        *state.python_child.lock().unwrap() = Some(child);
                    }

                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line_bytes) => {
                                let line = String::from_utf8_lossy(&line_bytes);
                                for sub_line in line.lines() {
                                    let sub_line = sub_line.trim();
                                    if sub_line.is_empty() { continue; }
                                    
                                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(sub_line) {
                                        let state_lock = app_handle.state::<AppState>();
                                        
                                        match json["status"].as_str() {
                                            Some("detected") => {
                                                println!("Wake word detected!");
                                                play_wake_sound(&app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Listening;
                                                }
                                                if let Some(window) = app_handle.get_webview_window("main") {
                                                    let hwnd = window.hwnd().unwrap();
                                                    unsafe { let _ = ShowWindow(HWND(hwnd.0), SW_SHOWNA); }
                                                }
                                                app_handle.emit("orb-state-change", OrbState::Listening).unwrap();
                                            },
                                            Some("recording") => {
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Recording;
                                                }
                                                app_handle.emit("orb-state-change", OrbState::Recording).unwrap();
                                            },
                                            Some("transcribing") => {
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Processing;
                                                }
                                                app_handle.emit("orb-state-change", OrbState::Processing).unwrap();
                                            },
                                            Some("success") => {
                                                let text = json["text"].as_str().unwrap_or("");
                                                println!("Command executed: {}", text);
                                                play_success_sound(&app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Success;
                                                    app_handle.emit("orb-state-change", OrbState::Success).unwrap();
                                                }
                                                
                                                let h = app_handle.clone();
                                                tauri::async_runtime::spawn(async move {
                                                    tokio::time::sleep(std::time::Duration::from_secs(4)).await;
                                                    let state_lock = h.state::<AppState>();
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    if matches!(*s, OrbState::Success | OrbState::Error) {
                                                        *s = OrbState::Idle;
                                                        h.emit("orb-state-change", OrbState::Idle).unwrap();
                                                        if let Some(window) = h.get_webview_window("main") {
                                                            let _ = window.hide();
                                                        }
                                                    }
                                                });
                                            },
                                            Some("error") => {
                                                play_error_sound(&app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Error;
                                                }
                                                app_handle.emit("orb-state-change", OrbState::Error).unwrap();
                                                
                                                let h = app_handle.clone();
                                                tauri::async_runtime::spawn(async move {
                                                    tokio::time::sleep(std::time::Duration::from_secs(7)).await;
                                                    let state_lock = h.state::<AppState>();
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    if matches!(*s, OrbState::Error) {
                                                        *s = OrbState::Idle;
                                                        h.emit("orb-state-change", OrbState::Idle).unwrap();
                                                        if let Some(window) = h.get_webview_window("main") {
                                                            let _ = window.hide();
                                                        }
                                                    }
                                                });
                                            },
                                            Some("ready") => {
                                                let mut s = state_lock.state.lock().unwrap();
                                                if !matches!(*s, OrbState::Success | OrbState::Error | OrbState::Processing | OrbState::Listening | OrbState::Recording) {
                                                    *s = OrbState::Idle;
                                                    app_handle.emit("orb-state-change", OrbState::Idle).unwrap();
                                                }
                                            },
                                            Some("media_control") => {
                                                let cmd = json["command"].as_str().unwrap_or("toggle");
                                                let _h = app_handle.clone();
                                                let cmd_string = cmd.to_string();
                                                tauri::async_runtime::spawn(async move {
                                                    let _ = media_command(cmd_string).await;
                                                });
                                            },
                                            Some("hide") => {
                                                if let Some(window) = app_handle.get_webview_window("main") {
                                                    let _ = window.hide();
                                                }
                                            },
                                            _ => {}
                                        }
                                    }
                                }
                            },
                            CommandEvent::Stderr(line_bytes) => {
                                let line = String::from_utf8_lossy(&line_bytes);
                                eprintln!("STT Error: {}", line);
                            },
                            CommandEvent::Terminated(payload) => {
                                eprintln!("STT process terminated with code {:?}. Restarting in 3s...", payload.code);
                                break; // Exit the while loop to restart
                            },
                            _ => {}
                        }
                    }
                    
                    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![toggle_playback, media_command])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
