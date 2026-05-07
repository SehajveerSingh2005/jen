use serde::Serialize;
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

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

struct AppState {
    state: Mutex<OrbState>,
}

use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};

fn execute_command(text: &str) -> Result<(), String> {
    let text = text.to_lowercase();
    println!("Executing command for: {}", text);
    
    if text.contains("open") || text.contains("launch") || text.contains("start") {
        let app = text
            .replace("open", "")
            .replace("launch", "")
            .replace("start", "")
            .trim()
            .to_string();
            
        if !app.is_empty() {
            println!("Attempting to start app: {}", app);
            
            // 1. Try common Windows paths if direct 'start' fails
            let user_profile = std::env::var("USERPROFILE").unwrap_or_default();
            let common_apps = [
                ("notion", vec![
                    format!("{}\\AppData\\Local\\Programs\\Notion\\Notion.exe", user_profile),
                ]),
                ("discord", vec![
                    format!("{}\\AppData\\Local\\Discord\\Update.exe --processStart Discord.exe", user_profile),
                ]),
                ("chrome", vec!["chrome.exe".to_string()]),
                ("spotify", vec!["spotify.exe".to_string()]),
            ];

            for (key, paths) in &common_apps {
                if app.contains(*key) {
                    for p in paths {
                        if std::process::Command::new("cmd")
                            .args(["/C", "start", "", p])
                            .spawn()
                            .is_ok() {
                            return Ok(());
                        }
                    }
                }
            }

            // 2. Fallback to generic start
            let cmd = format!("start /B \"\" \"{}\" || start /B \"\" \"{}.exe\"", app, app);
            std::process::Command::new("cmd")
                .args(["/C", &cmd])
                .spawn()
                .map_err(|e| e.to_string())?;
            return Ok(());
        }
    }

    if text.contains("volume up") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("volume down") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("mute") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("pause") || text.contains("stop music") || text.contains("stop audio") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]179)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("resume") || text.contains("play music") || text.contains("play audio") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]179)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("next") || text.contains("skip") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]176)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("previous") || text.contains("back") {
        std::process::Command::new("powershell")
            .args(["-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]177)"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else if text.contains("search google for") {
        let query = text.replace("search google for", "").trim().to_string();
        let url = format!("https://www.google.com/search?q={}", query);
        std::process::Command::new("cmd")
            .args(["/C", &format!("start \"\" \"{}\"", url)])
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            state: Mutex::new(OrbState::Idle),
        })
        .setup(|app| {
            let app_handle = app.handle().clone();
            
            // Setup System Tray
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&quit_i])?;
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| {
                    if event.id == "quit" {
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

            // Start the persistent Python sidecar
            tauri::async_runtime::spawn(async move {
                let shell = app_handle.shell();
                let (mut rx, _child) = shell.command("python")
                    .args(["-u", "stt.py"]) // -u for unbuffered output
                    .spawn()
                    .expect("Failed to spawn Python STT sidecar");

                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(line_bytes) = event {
                        let line = String::from_utf8_lossy(&line_bytes);
                        for sub_line in line.lines() {
                            let sub_line = sub_line.trim();
                            if sub_line.is_empty() { continue; }
                            
                            println!("Python: {}", sub_line);
                            
                            if let Ok(json) = serde_json::from_str::<serde_json::Value>(sub_line) {
                                let state_lock = app_handle.state::<AppState>();
                                
                                match json["status"].as_str() {
                                    Some("detected") => {
                                        println!("Wake word detected!");
                                        {
                                            let mut s = state_lock.state.lock().unwrap();
                                            *s = OrbState::Listening;
                                        }
                                        if let Some(window) = app_handle.get_webview_window("main") {
                                            let _ = window.show();
                                            let _ = window.set_ignore_cursor_events(false);
                                            let _ = window.set_focus();
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
                                        println!("Command: {}", text);
                                        
                                        {
                                            let mut s = state_lock.state.lock().unwrap();
                                            if let Err(e) = execute_command(text) {
                                                println!("Command execution failed: {}", e);
                                                *s = OrbState::Error;
                                                app_handle.emit("orb-state-change", OrbState::Error).unwrap();
                                            } else {
                                                *s = OrbState::Success;
                                                app_handle.emit("orb-state-change", OrbState::Success).unwrap();
                                            }
                                        }
                                        
                                        // Wait 7 seconds then hide
                                        let h = app_handle.clone();
                                        tauri::async_runtime::spawn(async move {
                                            tokio::time::sleep(std::time::Duration::from_secs(7)).await;
                                            
                                            let state_lock = h.state::<AppState>();
                                            let mut s = state_lock.state.lock().unwrap();
                                            
                                            // Only hide if we are still in Success or Error (haven't been re-triggered)
                                            if matches!(*s, OrbState::Success | OrbState::Error) {
                                                *s = OrbState::Idle;
                                                h.emit("orb-state-change", OrbState::Idle).unwrap();
                                                if let Some(window) = h.get_webview_window("main") {
                                                    let _ = window.hide();
                                                    let _ = window.set_ignore_cursor_events(true);
                                                }
                                            }
                                        });
                                    },
                                    Some("error") => {
                                        println!("STT Error: {}", json["message"]);
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
                                                    let _ = window.set_ignore_cursor_events(true);
                                                }
                                            }
                                        });
                                    },
                                    Some("ready") => {
                                        // When Python says ready, we only transition to Idle if we aren't currently 
                                        // in Success/Error/Processing/Listening/Recording.
                                        // This prevents the "jumping back to listening" bug.
                                        let mut s = state_lock.state.lock().unwrap();
                                        if !matches!(*s, OrbState::Success | OrbState::Error | OrbState::Processing | OrbState::Listening | OrbState::Recording) {
                                            *s = OrbState::Idle;
                                            app_handle.emit("orb-state-change", OrbState::Idle).unwrap();
                                        }
                                    },
                                    _ => {}
                                }
                            }
                        }
                    } else if let CommandEvent::Stderr(line_bytes) = event {
                        let line = String::from_utf8_lossy(&line_bytes);
                        eprintln!("Python Error: {}", line);
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
