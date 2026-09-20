use serde::Deserialize;
use serde::Serialize;
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_store::StoreExt;

use windows::Media::Control::GlobalSystemMediaTransportControlsSessionManager;
use windows::Win32::Foundation::{HWND, RECT};
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowLongW, GetWindowRect, SetWindowLongW, SetWindowPos, ShowWindow, GWL_EXSTYLE,
    HWND_TOP, SWP_FRAMECHANGED, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER,
    SW_SHOWNA, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
};

use base64::Engine;
use rodio::{Decoder, OutputStream, OutputStreamHandle, Sink, Source};
use std::io::Cursor;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
#[cfg(not(any(target_os = "android", target_os = "ios")))]
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_updater::UpdaterExt;

#[derive(Debug, Clone, Serialize, Copy)]
#[serde(rename_all = "lowercase")]
pub enum OrbState {
    Idle,
    Startup,
    Listening,
    Recording,
    Processing,
    Success,
    Error,
    Speaking,
}

struct SendSyncWrapper<T>(T);
unsafe impl<T> Send for SendSyncWrapper<T> {}
unsafe impl<T> Sync for SendSyncWrapper<T> {}

struct AppState {
    pub state: Mutex<OrbState>,
    pub python_child: Mutex<Option<CommandChild>>,
    pub llama_child: Mutex<Option<CommandChild>>,
    pub audio_handle: Mutex<OutputStreamHandle>,
    pub audio_feedback: Mutex<bool>,
    pub current_shortcut: Mutex<Option<Shortcut>>,
    pub _audio_stream: Mutex<SendSyncWrapper<OutputStream>>,
    pub tts_sink: Mutex<Option<Sink>>,
    pub tts_enabled: Mutex<bool>,
    pub input_devices: Mutex<Vec<serde_json::Value>>,
    pub custom_output_device: Mutex<Option<String>>,
}

const LLAMA_PORT: u16 = 58931;

fn llama_base_url() -> String {
    format!("http://127.0.0.1:{}/v1", LLAMA_PORT)
}

/// Optional GPU (Vulkan) llama-server build, installed on demand by the user.
fn gpu_runtime_dir(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
    app.path().app_data_dir().ok().map(|d| d.join("llama-vulkan"))
}

fn gpu_runtime_exe(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
    let exe = gpu_runtime_dir(app)?.join("llama-server.exe");
    exe.exists().then_some(exe)
}

fn gpu_accel_enabled(app: &tauri::AppHandle) -> bool {
    app.store("settings.json")
        .ok()
        .and_then(|s| s.get("gpu_accel").and_then(|v| v.as_bool()))
        .unwrap_or(false)
}

/// Spawn the bundled llama-server with the given GGUF model.
/// Kills any previously running instance first (model switch / restart).
fn spawn_llama_server(app: &tauri::AppHandle, model_path: &str) -> Result<(), String> {
    let threads = std::thread::available_parallelism()
        .map(|n| n.get().saturating_sub(2).max(2))
        .unwrap_or(4);
    let port = LLAMA_PORT.to_string();

    // Kill stale llama-server processes left behind by a crashed or
    // hot-reloaded run. They are not children of this process, so they would
    // otherwise hold the port and waste memory (observed: 1.7 GB orphans).
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let _ = std::process::Command::new("taskkill")
            .args(["/IM", "llama-server.exe", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
    }

    // Prefer the GPU build when enabled and installed. Its exe lives next to
    // its own DLLs in app data, so Windows resolves them from the exe dir.
    let gpu_exe = if gpu_accel_enabled(app) {
        let exe = gpu_runtime_exe(app);
        if exe.is_none() {
            eprintln!("gpu_accel is on but no GPU runtime found; using CPU build");
        }
        exe
    } else {
        None
    };

    let cmd = match &gpu_exe {
        Some(exe) => app.shell().command(exe.to_string_lossy().to_string()),
        None => {
            // In dev mode, DLLs live in src-tauri/binaries/ but the sidecar exe
            // runs from target/debug/. Append the binaries dir to PATH so
            // Windows can locate them at load time.
            let mut cpucmd = app
                .shell()
                .sidecar("llama-server")
                .map_err(|e| e.to_string())?;
            if let Ok(mut path) = std::env::var("PATH") {
                if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
                    let binaries = std::path::Path::new(manifest_dir).join("binaries");
                    path.push(';');
                    path.push_str(binaries.to_string_lossy().as_ref());
                }
                cpucmd = cpucmd.env("PATH", path);
            }
            cpucmd
        }
    };

    let mut args: Vec<String> = vec![
        "--model".into(), model_path.into(),
        "--alias".into(), "jen-local".into(),
        "--host".into(), "127.0.0.1".into(),
        "--port".into(), port,
        "--ctx-size".into(), "4096".into(),
        "--threads".into(), threads.to_string(),
        "--jinja".into(),
        "--no-webui".into(),
    ];
    if gpu_exe.is_some() {
        args.push("--n-gpu-layers".into());
        args.push("99".into());
    }

    let (mut rx, child) = cmd
        .args(args)
        .spawn()
        .map_err(|e| format!("failed to spawn llama-server: {}", e))?;

    {
        let state = app.state::<AppState>();
        let mut guard = state.llama_child.lock().unwrap();
        if let Some(old) = guard.take() {
            let _ = old.kill();
        }
        *guard = Some(child);
    }
    println!(
        "llama-server spawned ({}) with model: {}",
        if gpu_exe.is_some() { "GPU/Vulkan" } else { "CPU" },
        model_path
    );

    // Drain stdout/stderr so the child never blocks on a full pipe
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stderr(b) => {
                    eprintln!("[llama] {}", String::from_utf8_lossy(&b).trim())
                }
                CommandEvent::Stdout(b) => {
                    println!("[llama] {}", String::from_utf8_lossy(&b).trim())
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[llama] terminated with code {:?}", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    // Wait for health, then tell the Python sidecar where to reach the brain
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let client = reqwest::Client::new();
        let health_url = format!("http://127.0.0.1:{}/health", LLAMA_PORT);
        for _ in 0..120 {
            let healthy = client
                .get(&health_url)
                .timeout(std::time::Duration::from_millis(500))
                .send()
                .await
                .map(|r| r.status().is_success())
                .unwrap_or(false);
            if healthy {
                println!("llama-server healthy on port {}", LLAMA_PORT);
                let state = app_handle.state::<AppState>();
                let msg = format!("ai_local_url:{}\n", llama_base_url());
                let mut guard = state.python_child.lock().unwrap();
                if let Some(child) = guard.as_mut() {
                    let _ = child.write(msg.as_bytes());
                }
                return;
            }
            tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        }
        eprintln!("llama-server did not become healthy within 60s");
    });

    Ok(())
}

fn stop_llama_server(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    let mut guard = state.llama_child.lock().unwrap();
    if let Some(child) = guard.take() {
        let _ = child.kill();
        println!("llama-server stopped");
    }
}

/// Transparent undecorated windows occasionally render with a ghost titlebar
/// or an opaque background after being shown or regaining focus (upstream
/// WebView2 bug: tauri#14764, tauri#14859). Forcing a frame recalculation
/// clears it; a 1px size nudge makes WebView2 recomposite.
fn refresh_window_chrome(hwnd: HWND, nudge: bool) {
    unsafe {
        let _ = SetWindowPos(
            hwnd,
            Some(HWND_TOP),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        );
        if nudge {
            let mut rect = RECT::default();
            if GetWindowRect(hwnd, &mut rect).is_ok() {
                let w = rect.right - rect.left;
                let h = rect.bottom - rect.top;
                let _ = SetWindowPos(
                    hwnd,
                    Some(HWND_TOP),
                    0,
                    0,
                    w + 1,
                    h,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
                );
                let _ = SetWindowPos(
                    hwnd,
                    Some(HWND_TOP),
                    0,
                    0,
                    w,
                    h,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
                );
            }
        }
    }
}

/// Show the orb window without stealing focus, then refresh the chrome.
fn show_orb_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if let Ok(hwnd) = window.hwnd() {
            unsafe {
                let _ = ShowWindow(HWND(hwnd.0), SW_SHOWNA);
            }
            refresh_window_chrome(HWND(hwnd.0), true);
        }
    }
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
    if *state.audio_feedback.lock().unwrap() {
        let handle = state.audio_handle.lock().unwrap();
        play_sound(&handle, WAKE_MP3);
    }
}

fn play_success_sound(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    if *state.audio_feedback.lock().unwrap() {
        let handle = state.audio_handle.lock().unwrap();
        play_sound(&handle, SUCCESS_MP3);
    }
}

fn play_error_sound(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    if *state.audio_feedback.lock().unwrap() {
        let handle = state.audio_handle.lock().unwrap();
        play_sound(&handle, ERROR_MP3);
    }
}

#[derive(Serialize)]
struct UpdateInfo {
    available: bool,
    version: Option<String>,
    body: Option<String>,
}

#[tauri::command]
fn get_app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
async fn check_for_update(app: tauri::AppHandle) -> Result<UpdateInfo, String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    let update = updater.check().await.map_err(|e| e.to_string())?;
    
    if let Some(update) = update {
        Ok(UpdateInfo {
            available: true,
            version: Some(update.version.clone()),
            body: update.body.clone(),
        })
    } else {
        Ok(UpdateInfo {
            available: false,
            version: None,
            body: None,
        })
    }
}

#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    let update = updater.check().await.map_err(|e| e.to_string())?;
    
    if let Some(update) = update {
        update.download_and_install(|_chunk_length, _pending_length| {}, || {})
            .await
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[derive(Deserialize)]
struct DownloadRequest {
    url: String,
    path: String,
}

#[tauri::command]
async fn download_file(app: tauri::AppHandle, request: DownloadRequest) -> Result<String, String> {
    use futures_util::StreamExt;

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(300))
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .get(&request.url)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if !response.status().is_success() {
        return Err(format!("HTTP error: {}", response.status()));
    }

    let total_size = response.content_length().unwrap_or(0);
    let mut stream = response.bytes_stream();

    // Create parent directory if needed
    if let Some(parent) = std::path::Path::new(&request.path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let mut file = std::fs::File::create(&request.path).map_err(|e| e.to_string())?;
    let mut downloaded: u64 = 0;
    let mut last_pct = 0u32;

    let result = async {
        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|e| e.to_string())?;
            std::io::Write::write_all(&mut file, &chunk).map_err(|e| e.to_string())?;
            downloaded += chunk.len() as u64;

            if total_size > 0 {
                let pct = ((downloaded as f64 / total_size as f64) * 100.0) as u32;
                if pct != last_pct {
                    last_pct = pct;
                    let _ = app.emit("download-progress", serde_json::json!({
                        "path": &request.path,
                        "progress": pct,
                        "downloaded": downloaded,
                        "total": total_size,
                    }));
                }
            }
        }
        Ok::<(), String>(())
    }.await;

    if result.is_err() {
        // Clean up partial file on error
        let _ = std::fs::remove_file(&request.path);
        return result.map(|_| request.path);
    }

    Ok(request.path)
}

#[tauri::command]
fn file_exists(path: String) -> bool {
    std::path::Path::new(&path).exists()
}

#[tauri::command]
fn delete_file(path: String) -> Result<(), String> {
    std::fs::remove_file(&path).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_audio_feedback(state: tauri::State<'_, AppState>, enabled: bool) {
    let mut guard = state.audio_feedback.lock().unwrap();
    *guard = enabled;
}

#[tauri::command]
fn set_sensitive_protection(state: tauri::State<'_, AppState>, enabled: bool) {
    let msg = if enabled { b"protect:1\n" as &[u8] } else { b"protect:0\n" };
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg);
    }
}

#[tauri::command]
fn set_tts_enabled(state: tauri::State<'_, AppState>, enabled: bool) {
    {
        let mut guard = state.tts_enabled.lock().unwrap();
        *guard = enabled;
    }
    let msg = if enabled { b"tts:1\n" as &[u8] } else { b"tts:0\n" };
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg);
    }
}

#[tauri::command]
fn set_tts_voice(state: tauri::State<'_, AppState>, voice: String) {
    let msg = format!("tts_voice:{}\n", voice);
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
fn preview_voice(state: tauri::State<'_, AppState>, voice: String) {
    let msg = format!("preview_voice:{}\n", voice);
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
fn set_ai_mode(app: tauri::AppHandle, mode: String) {
    {
        let state = app.state::<AppState>();
        let msg = format!("ai_mode:{}\n", mode);
        let mut child_guard = state.python_child.lock().unwrap();
        if let Some(child) = child_guard.as_mut() {
            let _ = child.write(msg.as_bytes());
        }
    }

    // Rust owns the local LLM lifecycle
    if mode == "local" {
        let model_path = app
            .store("settings.json")
            .ok()
            .and_then(|s| s.get("ai_local_model"))
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_default();
        if !model_path.is_empty() && std::path::Path::new(&model_path).exists() {
            if let Err(e) = spawn_llama_server(&app, &model_path) {
                eprintln!("failed to start llama-server: {}", e);
            }
        }
    } else {
        stop_llama_server(&app);
    }
}

#[tauri::command]
fn set_ai_local_model(app: tauri::AppHandle, model_path: String) {
    // The model path is consumed by llama-server (Rust-side), not Python.
    // Restart the server with the new model if local mode is active.
    let mode = app
        .store("settings.json")
        .ok()
        .and_then(|s| s.get("ai_mode"))
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_else(|| "off".to_string());

    if model_path.is_empty() {
        stop_llama_server(&app);
    } else if mode == "local" && std::path::Path::new(&model_path).exists() {
        if let Err(e) = spawn_llama_server(&app, &model_path) {
            eprintln!("failed to restart llama-server: {}", e);
        }
    }
}

#[tauri::command]
fn set_personality(state: tauri::State<'_, AppState>, personality: String) {
    let msg = format!("personality:{}\n", personality);
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
fn set_followup_enabled(state: tauri::State<'_, AppState>, enabled: bool) {
    let msg = if enabled { "followup:1\n" } else { "followup:0\n" };
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
fn set_wake_sensitivity(state: tauri::State<'_, AppState>, value: String) {
    let msg = format!("wake_sensitivity:{}\n", value);
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
fn gpu_status(app: tauri::AppHandle) -> serde_json::Value {
    let installed = gpu_runtime_exe(&app).is_some();
    let enabled = gpu_accel_enabled(&app);
    serde_json::json!({ "installed": installed, "enabled": enabled })
}

/// Restart llama-server if local AI mode is active (used after GPU toggle).
fn restart_llama_if_local(app: &tauri::AppHandle) {
    let store = app.store("settings.json").ok();
    let mode = store
        .as_ref()
        .and_then(|s| s.get("ai_mode"))
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_else(|| "off".to_string());
    let model = store
        .as_ref()
        .and_then(|s| s.get("ai_local_model"))
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_default();
    if mode == "local" && !model.is_empty() && std::path::Path::new(&model).exists() {
        if let Err(e) = spawn_llama_server(app, &model) {
            eprintln!("llama-server restart failed: {}", e);
        }
    }
}

#[tauri::command]
fn set_gpu_accel(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let store = app.store("settings.json").map_err(|e| e.to_string())?;
    store.set("gpu_accel", serde_json::json!(enabled));
    store.save().map_err(|e| e.to_string())?;
    println!("gpu acceleration {}", if enabled { "enabled" } else { "disabled" });
    restart_llama_if_local(&app);
    Ok(())
}

/// Extract a downloaded GPU llama-server zip into the app data runtime dir.
#[tauri::command]
fn install_gpu_runtime(app: tauri::AppHandle, zip_path: String) -> Result<(), String> {
    let dir = gpu_runtime_dir(&app).ok_or_else(|| "no app data dir".to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    if !std::path::Path::new(&zip_path).exists() {
        return Err(format!("zip not found: {}", zip_path));
    }

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let script = format!(
            "Expand-Archive -LiteralPath '{}' -DestinationPath '{}' -Force",
            zip_path.replace('\'', "''"),
            dir.to_string_lossy().replace('\'', "''"),
        );
        let out = std::process::Command::new("powershell")
            .args(["-NoProfile", "-NonInteractive", "-Command", &script])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map_err(|e| format!("failed to run powershell: {}", e))?;
        if !out.status.success() {
            return Err(format!(
                "extraction failed: {}",
                String::from_utf8_lossy(&out.stderr)
            ));
        }
    }

    if gpu_runtime_exe(&app).is_none() {
        return Err("llama-server.exe not found after extraction".to_string());
    }
    let _ = std::fs::remove_file(&zip_path);
    println!("GPU runtime installed to {}", dir.display());
    Ok(())
}

#[tauri::command]
fn list_audio_devices(app: tauri::AppHandle, state: tauri::State<'_, AppState>) -> serde_json::Value {
    use rodio::cpal::traits::{DeviceTrait, HostTrait};

    let inputs = state.input_devices.lock().unwrap().clone();

    let host = rodio::cpal::default_host();
    let outputs: Vec<String> = host
        .output_devices()
        .map(|devs| devs.filter_map(|d| d.name().ok()).collect())
        .unwrap_or_default();

    let store = app.store("settings.json").ok();
    let current_input = store
        .as_ref()
        .and_then(|s| s.get("audio_input_device"))
        .and_then(|v| v.as_i64());
    let current_output = store
        .as_ref()
        .and_then(|s| s.get("audio_output_device"))
        .and_then(|v| v.as_str().map(String::from));

    serde_json::json!({
        "inputs": inputs,
        "outputs": outputs,
        "current_input": current_input,
        "current_output": current_output,
    })
}

#[tauri::command]
fn set_input_device(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    index: Option<i64>,
) -> Result<(), String> {
    let store = app.store("settings.json").map_err(|e| e.to_string())?;
    store.set("audio_input_device", serde_json::json!(index));
    store.save().map_err(|e| e.to_string())?;

    let msg = match index {
        Some(i) => format!("input_device:{}\n", i),
        None => "input_device:default\n".to_string(),
    };
    let mut guard = state.python_child.lock().unwrap();
    if let Some(child) = guard.as_mut() {
        child.write(msg.as_bytes()).map_err(|e| e.to_string())?;
    }
    println!(
        "input device set to {}",
        index.map(|i| i.to_string()).unwrap_or_else(|| "default".into())
    );
    Ok(())
}

#[tauri::command]
fn set_output_device(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    name: Option<String>,
) -> Result<(), String> {
    use rodio::cpal::traits::{DeviceTrait, HostTrait};

    let (new_stream, new_handle) = match &name {
        Some(device_name) => {
            let host = rodio::cpal::default_host();
            let device = host
                .output_devices()
                .map_err(|e| e.to_string())?
                .find(|d| d.name().ok().as_deref() == Some(device_name.as_str()))
                .ok_or_else(|| format!("output device not found: {}", device_name))?;
            OutputStream::try_from_device(&device).map_err(|e| e.to_string())?
        }
        None => OutputStream::try_default().map_err(|e| e.to_string())?,
    };

    {
        let mut stream_guard = state._audio_stream.lock().unwrap();
        *stream_guard = SendSyncWrapper(new_stream);
    }
    {
        let mut handle_guard = state.audio_handle.lock().unwrap();
        *handle_guard = new_handle;
    }
    if let Some(sink) = state.tts_sink.lock().unwrap().take() {
        sink.stop();
    }
    *state.custom_output_device.lock().unwrap() = name.clone();

    let store = app.store("settings.json").map_err(|e| e.to_string())?;
    store.set("audio_output_device", serde_json::json!(name));
    store.save().map_err(|e| e.to_string())?;
    println!("output device set to {}", name.as_deref().unwrap_or("default"));
    Ok(())
}

#[tauri::command]
fn set_ai_cloud(
    state: tauri::State<'_, AppState>,
    api_key: String,
    base_url: String,
    model: String,
) {
    let msg = format!("ai_cloud:{}:{}:{}\n", api_key, base_url, model);
    let mut child_guard = state.python_child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        let _ = child.write(msg.as_bytes());
    }
}

#[tauri::command]
async fn toggle_playback() -> Result<(), String> {
    let manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync()
        .map_err(|e| e.to_string())?
        .await
        .map_err(|e| e.to_string())?;

    if let Ok(session) = manager.GetCurrentSession() {
        let _ = session
            .TryTogglePlayPauseAsync()
            .map_err(|e| e.to_string())?
            .await;
    }
    Ok(())
}

#[tauri::command]
async fn media_command(command: String) -> Result<(), String> {
    let manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync()
        .map_err(|e| e.to_string())?
        .await
        .map_err(|e| e.to_string())?;

    if let Ok(session) = manager.GetCurrentSession() {
        match command.as_str() {
            "next" => {
                let _ = session.TrySkipNextAsync().map_err(|e| e.to_string())?.await;
            }
            "prev" => {
                let _ = session
                    .TrySkipPreviousAsync()
                    .map_err(|e| e.to_string())?
                    .await;
            }
            "play" => {
                let _ = session.TryPlayAsync().map_err(|e| e.to_string())?.await;
            }
            "pause" => {
                let _ = session.TryPauseAsync().map_err(|e| e.to_string())?.await;
            }
            _ => {}
        }
    }
    Ok(())
}

#[tauri::command]
async fn register_shortcut(app: tauri::AppHandle, shortcut_str: String) -> Result<(), String> {
    use std::str::FromStr;

    let shortcut = Shortcut::from_str(&shortcut_str).map_err(|e| e.to_string())?;
    
    let state = app.state::<AppState>();
    
    // Unregister all existing shortcuts
    let _ = app.global_shortcut().unregister_all();
    
    // Register the new shortcut
    app.global_shortcut().register(shortcut).map_err(|e| e.to_string())?;

    // Store the new shortcut in state
    let mut current = state.current_shortcut.lock().unwrap();
    *current = Some(shortcut);

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Initialize audio output stream and handle
    let (audio_stream, audio_handle) =
        OutputStream::try_default().expect("Failed to initialize audio output");

    let mut builder = tauri::Builder::default();

    #[cfg(not(any(target_os = "android", target_os = "ios")))]
    {
        builder = builder.plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None));
    }

    builder
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, triggered_shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        let state = app.state::<AppState>();
                        let current_shortcut_guard = state.current_shortcut.lock().unwrap();
                        
                        if let Some(ref current) = *current_shortcut_guard {
                            if triggered_shortcut == current {
                                let mut python_child_guard = state.python_child.lock().unwrap();
                                if let Some(child) = python_child_guard.as_mut() {
                                    match child.write(b"trigger\n") {
                                        Ok(_) => println!("Manual trigger via hotkey sent to Python"),
                                        Err(e) => eprintln!("Failed to send manual trigger to Python: {}", e),
                                    }
                                } else {
                                    eprintln!("Manual trigger ignored: Python sidecar not running");
                                }
                            }
                        }
                    }
                })
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .on_window_event(|window, event| {
            // Transparent undecorated windows can grow a ghost titlebar when
            // they regain focus (upstream WebView2 bug, tauri#14764/#14859).
            if window.label() == "main" {
                if let tauri::WindowEvent::Focused(true) = event {
                    if let Ok(hwnd) = window.hwnd() {
                        refresh_window_chrome(HWND(hwnd.0), false);
                    }
                }
            }
        })
        .manage(AppState {
            state: Mutex::new(OrbState::Idle),
            python_child: Mutex::new(None),
            llama_child: Mutex::new(None),
            audio_handle: Mutex::new(audio_handle),
            audio_feedback: Mutex::new(true),
            current_shortcut: Mutex::new(None),
            _audio_stream: Mutex::new(SendSyncWrapper(audio_stream)),
            tts_sink: Mutex::new(None),
            tts_enabled: Mutex::new(true),
            input_devices: Mutex::new(Vec::new()),
            custom_output_device: Mutex::new(None),
        })
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // Check for updates on launch
            let update_app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                // Wait 6 seconds for main window startup to settle
                tokio::time::sleep(std::time::Duration::from_secs(6)).await;
                if let Ok(updater) = update_app_handle.updater() {
                    if let Ok(Some(update)) = updater.check().await {
                        println!("Auto-update check on launch: new update available (v{})", update.version);
                        let app = update_app_handle.clone();
                        let app_inner = app.clone();
                        let _ = app.run_on_main_thread(move || {
                            if let Some(window) = app_inner.get_webview_window("settings") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            } else {
                                let _ = tauri::WebviewWindowBuilder::new(
                                    &app_inner,
                                    "settings",
                                    tauri::WebviewUrl::App("settings.html".into()),
                                )
                                .title("Jen Settings")
                                .inner_size(520.0, 500.0)
                                .resizable(false)
                                .decorations(false)
                                .build();
                            }
                        });
                    }
                }
            });

            // Spawn audio output monitor
            let audio_app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                use rodio::cpal::traits::{HostTrait, DeviceTrait};

                // Helper to get default device ID
                let get_default_id = || {
                    let host = rodio::cpal::default_host();
                    host.default_output_device().and_then(|d| d.name().ok())
                };

                let mut current_device_id = get_default_id();

                loop {
                    tokio::time::sleep(std::time::Duration::from_secs(5)).await;

                    // A user-selected output device takes precedence over
                    // tracking the system default.
                    {
                        let state = audio_app_handle.state::<AppState>();
                        if state.custom_output_device.lock().unwrap().is_some() {
                            continue;
                        }
                    }

                    let new_id = get_default_id();
                    if new_id != current_device_id {
                        println!("Default audio output device changed to: {:?}. Refreshing...", new_id);
                        match OutputStream::try_default() {
                            Ok((new_stream, new_handle)) => {
                                let state = audio_app_handle.state::<AppState>();
                                {
                                    let mut stream_guard = state._audio_stream.lock().unwrap();
                                    *stream_guard = SendSyncWrapper(new_stream);
                                }
                                {
                                    let mut handle_guard = state.audio_handle.lock().unwrap();
                                    *handle_guard = new_handle;
                                }
                                current_device_id = new_id;
                                println!("Audio output stream refreshed successfully.");
                            }
                            Err(e) => {
                                eprintln!("Failed to refresh audio output stream: {}", e);
                            }
                        }
                    }
                }
            });

            // Load saved settings
            if let Ok(store) = app_handle.store("settings.json") {
                let state = app_handle.state::<AppState>();

                // Apply audio feedback setting
                if let Some(audio_feedback) = store.get("audio_feedback") {
                    if let Some(enabled) = audio_feedback.as_bool() {
                        let mut guard = state.audio_feedback.lock().unwrap();
                        *guard = enabled;
                    }
                }

                // Apply saved output device (user-selected speaker)
                if let Some(dev_name) = store
                    .get("audio_output_device")
                    .and_then(|v| v.as_str().map(String::from))
                {
                    if let Err(e) = set_output_device(
                        app_handle.clone(),
                        app_handle.state(),
                        Some(dev_name.clone()),
                    ) {
                        eprintln!("failed to apply saved output device {}: {}", dev_name, e);
                    }
                }

                // Apply activation hotkey
                if let Some(hotkey_val) = store.get("activation_hotkey") {
                    if let Some(hotkey_str) = hotkey_val.as_str() {
                        use std::str::FromStr;
                        if let Ok(shortcut) = Shortcut::from_str(hotkey_str) {
                            let _ = app_handle.global_shortcut().register(shortcut);
                            let mut current = state.current_shortcut.lock().unwrap();
                            *current = Some(shortcut);
                        }
                    }
                } else {
                    // Register default shortcut if none saved
                    use std::str::FromStr;
                    let default_hotkey = "Ctrl+Shift+R";
                    if let Ok(shortcut) = Shortcut::from_str(default_hotkey) {
                        let _ = app_handle.global_shortcut().register(shortcut);
                        let mut current = state.current_shortcut.lock().unwrap();
                        *current = Some(shortcut);
                    }
                }
            } else {
                println!("No settings.json found or failed to load, using defaults.");
                // Register default shortcut
                let state = app_handle.state::<AppState>();
                use std::str::FromStr;
                let default_hotkey = "Ctrl+Shift+R";
                if let Ok(shortcut) = Shortcut::from_str(default_hotkey) {
                    let _ = app_handle.global_shortcut().register(shortcut);
                    let mut current = state.current_shortcut.lock().unwrap();
                    *current = Some(shortcut);
                }
            }

            // Setup System Tray
            let settings_i = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            
            #[cfg(not(any(target_os = "android", target_os = "ios")))]
            let autostart_enabled = app.autolaunch().is_enabled().unwrap_or(false);
            #[cfg(any(target_os = "android", target_os = "ios"))]
            let autostart_enabled = false;

            let autostart_i = CheckMenuItem::with_id(
                app,
                "autostart",
                "Launch on Startup",
                true,
                autostart_enabled,
                None::<&str>,
            )?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit Jen", true, None::<&str>)?;

            let menu = Menu::with_items(
                app,
                &[
                    &settings_i,
                    &autostart_i,
                    &PredefinedMenuItem::separator(app)?,
                    &quit_i,
                ],
            )?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "settings" => {
                        if let Some(window) = app.get_webview_window("settings") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        } else {
                            let _ = tauri::WebviewWindowBuilder::new(
                                app,
                                "settings",
                                tauri::WebviewUrl::App("settings.html".into()),
                            )
                            .title("Jen Settings")
                            .inner_size(520.0, 500.0)
                            .resizable(false)
                            .decorations(false)
                            .build();
                        }
                    }
                    "autostart" => {
                        #[cfg(not(any(target_os = "android", target_os = "ios")))]
                        {
                            let manager = app.autolaunch();
                            if manager.is_enabled().unwrap_or(false) {
                                let _ = manager.disable();
                                println!("Autostart disabled");
                            } else {
                                let _ = manager.enable();
                                println!("Autostart enabled");
                            }
                        }
                    }
                    "quit" => {
                        let state = app.state::<AppState>();
                        let mut python_child_guard = state.python_child.lock().unwrap();
                        if let Some(child) = python_child_guard.take() {
                            let _ = child.kill();
                            println!("STT Sidecar killed on exit.");
                        }
                        let mut llama_guard = state.llama_child.lock().unwrap();
                        if let Some(child) = llama_guard.take() {
                            let _ = child.kill();
                            println!("llama-server killed on exit.");
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event
                    {
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
                    let _ = SetWindowLongW(
                        HWND(hwnd.0),
                        GWL_EXSTYLE,
                        style | WS_EX_NOACTIVATE.0 as i32 | WS_EX_TOOLWINDOW.0 as i32,
                    );
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

                // Show window briefly on startup to signal activity
                let handle = app.handle().clone();
                let state_lock = handle.state::<AppState>();
                {
                    let mut s = state_lock.state.lock().unwrap();
                    *s = OrbState::Startup;
                }
                play_wake_sound(&handle);
                
                let _ = handle.emit("orb-state-change", "startup");
                
                unsafe {
                    let _ = ShowWindow(HWND(hwnd.0), SW_SHOWNA);
                }
                refresh_window_chrome(HWND(hwnd.0), true);
                
                tauri::async_runtime::spawn(async move {
                    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                    if let Some(window) = handle.get_webview_window("main") {
                        let state_lock = handle.state::<AppState>();
                        let mut s = state_lock.state.lock().unwrap();
                        // Only hide if we are still in startup phase (didn't get a wake word)
                        if matches!(*s, OrbState::Startup) {
                            *s = OrbState::Idle;
                            let _ = window.hide();
                            handle.emit("orb-state-change", "idle").unwrap();
                        }
                    }
                });
            }

            // Start the persistent STT sidecar with auto-restart logic
            let stt_app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                let shell = stt_app_handle.shell();

                loop {
                    println!("Spawning STT sidecar...");

                    // In dev mode (debug_assertions), prefer running the Python sidecar directly.
                    // In release/production, use the compiled sidecar executable.
                    #[cfg(debug_assertions)]
                    let cmd = if std::path::Path::new("src-tauri/sidecar/main.py").exists() {
                        shell.command("python").args(["-u", "src-tauri/sidecar/main.py"])
                    } else if std::path::Path::new("sidecar/main.py").exists() {
                        shell.command("python").args(["-u", "sidecar/main.py"])
                    } else {
                        shell.sidecar("stt").unwrap()
                    };

                    #[cfg(not(debug_assertions))]
                    let cmd = shell.sidecar("stt").unwrap_or_else(|_| {
                        if std::path::Path::new("src-tauri/sidecar/main.py").exists() {
                            shell.command("python").args(["-u", "src-tauri/sidecar/main.py"])
                        } else {
                            shell.command("python").args(["-u", "sidecar/main.py"])
                        }
                    });

                    let (mut rx, child) = cmd.spawn().expect("Failed to spawn STT process");

                    // Store the child handle and send initial protection state
                    {
                        let state = stt_app_handle.state::<AppState>();
                        let store = stt_app_handle.store("settings.json");

                        let protect_enabled = store.as_ref().ok()
                            .and_then(|s| s.get("sensitive_protection"))
                            .and_then(|v| v.as_bool())
                            .unwrap_or(true);

                        let tts_enabled_val = store.as_ref().ok()
                            .and_then(|s| s.get("tts_enabled"))
                            .and_then(|v| v.as_bool())
                            .unwrap_or(true);

                        let tts_voice_val = store.as_ref().ok()
                            .and_then(|s| s.get("tts_voice"))
                            .and_then(|v| v.as_str().map(String::from))
                            .unwrap_or_else(|| "en-US-JennyNeural".to_string());

                        {
                            let mut guard = state.tts_enabled.lock().unwrap();
                            *guard = tts_enabled_val;
                        }

                        let mut child_guard = state.python_child.lock().unwrap();
                        *child_guard = Some(child);
                        if let Some(ref mut c) = *child_guard {
                            let msg = if protect_enabled { b"protect:1\n" as &[u8] } else { b"protect:0\n" };
                            let _ = c.write(msg);
                            let msg = if tts_enabled_val { b"tts:1\n" as &[u8] } else { b"tts:0\n" };
                            let _ = c.write(msg);
                            let voice_msg = format!("tts_voice:{}\n", tts_voice_val);
                            let _ = c.write(voice_msg.as_bytes());

                            // Sync AI settings
                            let ai_mode_val = store.as_ref().ok()
                                .and_then(|s| s.get("ai_mode"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_else(|| "off".to_string());
                            let ai_msg = format!("ai_mode:{}\n", ai_mode_val);
                            let _ = c.write(ai_msg.as_bytes());

                            // Personality (minimal | conversational)
                            let personality = store.as_ref().ok()
                                .and_then(|s| s.get("personality"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_else(|| "minimal".to_string());
                            let msg = format!("personality:{}\n", personality);
                            let _ = c.write(msg.as_bytes());

                            // Follow-up conversation window (off by default)
                            let followup = store.as_ref().ok()
                                .and_then(|s| s.get("followup_enabled"))
                                .and_then(|v| v.as_bool())
                                .unwrap_or(false);
                            let msg = format!("followup:{}\n", if followup { 1 } else { 0 });
                            let _ = c.write(msg.as_bytes());

                            // Wake word sensitivity (low | medium | high)
                            let wake_sens = store.as_ref().ok()
                                .and_then(|s| s.get("wake_sensitivity"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_else(|| "medium".to_string());
                            let msg = format!("wake_sensitivity:{}\n", wake_sens);
                            let _ = c.write(msg.as_bytes());

                            // Persistent memory location (app data dir)
                            if let Ok(data_dir) = stt_app_handle.path().app_data_dir() {
                                let _ = std::fs::create_dir_all(&data_dir);
                                let mem_path = data_dir.join("memory.db");
                                let msg = format!("memory_path:{}\n", mem_path.to_string_lossy());
                                let _ = c.write(msg.as_bytes());
                            }

                            // Microphone selection (index or system default)
                            let input_dev = store.as_ref().ok()
                                .and_then(|s| s.get("audio_input_device"))
                                .and_then(|v| v.as_i64());
                            let input_msg = match input_dev {
                                Some(i) => format!("input_device:{}\n", i),
                                None => "input_device:default\n".to_string(),
                            };
                            let _ = c.write(input_msg.as_bytes());

                            let ai_api_key = store.as_ref().ok()
                                .and_then(|s| s.get("ai_cloud_api_key"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_default();
                            let ai_base_url = store.as_ref().ok()
                                .and_then(|s| s.get("ai_cloud_base_url"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_else(|| "https://api.openai.com/v1".to_string());
                            let ai_model = store.as_ref().ok()
                                .and_then(|s| s.get("ai_cloud_model"))
                                .and_then(|v| v.as_str().map(String::from))
                                .unwrap_or_else(|| "gpt-4o-mini".to_string());
                            if !ai_api_key.is_empty() {
                                let msg = format!("ai_cloud:{}:{}:{}\n", ai_api_key, ai_base_url, ai_model);
                                let _ = c.write(msg.as_bytes());
                            }
                        }
                    }


                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line_bytes) => {
                                let line = String::from_utf8_lossy(&line_bytes);
                                for sub_line in line.lines() {
                                    let sub_line = sub_line.trim();
                                    if sub_line.is_empty() {
                                        continue;
                                    }

                                    if let Ok(json) =
                                        serde_json::from_str::<serde_json::Value>(sub_line)
                                    {
                                        let state_lock = stt_app_handle.state::<AppState>();

                                        match json["status"].as_str() {
                                            Some("detected") => {
                                                let ww = json["wakeword"].as_str().unwrap_or("unknown");
                                                println!("Wake word detected: {}", ww);
                                                play_wake_sound(&stt_app_handle);
                                                // Barge-in: stop any TTS that is still speaking
                                                {
                                                    let mut tts_guard = state_lock.tts_sink.lock().unwrap();
                                                    if let Some(sink) = tts_guard.take() {
                                                        sink.stop();
                                                    }
                                                }
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Listening;
                                                }
                                                show_orb_window(&stt_app_handle);
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Listening)
                                                    .unwrap();
                                            }
                                            Some("recording") => {
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Recording;
                                                }
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Recording)
                                                    .unwrap();
                                            }
                                            Some("followup") => {
                                                // Follow-up window: show the orb as listening
                                                // without the wake chime
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Listening;
                                                }
                                                show_orb_window(&stt_app_handle);
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Listening)
                                                    .unwrap();
                                            }
                                            Some("transcribing") => {
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Processing;
                                                }
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Processing)
                                                    .unwrap();
                                            }
                                            Some("success") => {
                                                let text = json["text"].as_str().unwrap_or("");
                                                println!("Command executed: {}", text);
                                                play_success_sound(&stt_app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Success;
                                                    stt_app_handle
                                                        .emit("orb-state-change", OrbState::Success)
                                                        .unwrap();
                                                }

                                                let h = stt_app_handle.clone();
                                                tauri::async_runtime::spawn(async move {
                                                    tokio::time::sleep(
                                                        std::time::Duration::from_secs(4),
                                                    )
                                                    .await;
                                                    let state_lock = h.state::<AppState>();
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    if matches!(
                                                        *s,
                                                        OrbState::Success | OrbState::Error
                                                    ) {
                                                        *s = OrbState::Idle;
                                                        h.emit("orb-state-change", OrbState::Idle)
                                                            .unwrap();
                                                        if let Some(window) =
                                                            h.get_webview_window("main")
                                                        {
                                                            let _ = window.hide();
                                                        }
                                                    }
                                                });
                                            }
                                            Some("error") => {
                                                play_error_sound(&stt_app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Error;
                                                }
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Error)
                                                    .unwrap();

                                                let h = stt_app_handle.clone();
                                                tauri::async_runtime::spawn(async move {
                                                    tokio::time::sleep(
                                                        std::time::Duration::from_secs(7),
                                                    )
                                                    .await;
                                                    let state_lock = h.state::<AppState>();
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    if matches!(*s, OrbState::Error) {
                                                        *s = OrbState::Idle;
                                                        h.emit("orb-state-change", OrbState::Idle)
                                                            .unwrap();
                                                        if let Some(window) =
                                                            h.get_webview_window("main")
                                                        {
                                                            let _ = window.hide();
                                                        }
                                                    }
                                                });
                                            }
                                            Some("input_devices") => {
                                                if let Some(devices) = json["devices"].as_array() {
                                                    let mut guard =
                                                        state_lock.input_devices.lock().unwrap();
                                                    *guard = devices.clone();
                                                    println!(
                                                        "input devices enumerated: {} available",
                                                        devices.len()
                                                    );
                                                }
                                            }
                                            Some("ready") => {
                                                let mut s = state_lock.state.lock().unwrap();
                                                if !matches!(
                                                    *s,
                                                    OrbState::Success
                                                        | OrbState::Error
                                                        | OrbState::Processing
                                                        | OrbState::Listening
                                                        | OrbState::Recording
                                                ) {
                                                    *s = OrbState::Idle;
                                                    stt_app_handle
                                                        .emit("orb-state-change", OrbState::Idle)
                                                        .unwrap();
                                                }
                                            }
                                            Some("blocked_sensitive") => {
                                                println!("Sensitive command blocked (protection on): {}", json["text"].as_str().unwrap_or(""));
                                                play_error_sound(&stt_app_handle);
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Error;
                                                }
                                                stt_app_handle
                                                    .emit("orb-state-change", OrbState::Error)
                                                    .unwrap();
                                                let h = stt_app_handle.clone();
                                                tauri::async_runtime::spawn(async move {
                                                    tokio::time::sleep(
                                                        std::time::Duration::from_secs(4),
                                                    ).await;
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
                                            }
                                            Some("media_control") => {
                                                let cmd =
                                                    json["command"].as_str().unwrap_or("toggle");
                                                let _h = stt_app_handle.clone();
                                                let cmd_string = cmd.to_string();
                                                tauri::async_runtime::spawn(async move {
                                                    let _ = media_command(cmd_string).await;
                                                });
                                            }
                                            Some("hide") => {
                                                {
                                                    let mut s = state_lock.state.lock().unwrap();
                                                    *s = OrbState::Idle;
                                                }
                                                let _ = stt_app_handle
                                                    .emit("orb-state-change", OrbState::Idle);
                                                if let Some(window) =
                                                    stt_app_handle.get_webview_window("main")
                                                {
                                                    let _ = window.hide();
                                                }
                                            }
                                            Some("tts_audio") => {
                                                if let Some(b64_data) = json["data"].as_str() {
                                                    if let Ok(mp3_bytes) = base64::engine::general_purpose::STANDARD.decode(b64_data) {
                                                        let handle = stt_app_handle.state::<AppState>();
                                                        let audio_handle_guard = handle.audio_handle.lock().unwrap();
                                                        let cursor = std::io::Cursor::new(mp3_bytes.clone());
                                                        if let Ok(source) = Decoder::new(cursor) {
                                                            if let Ok(sink) = Sink::try_new(&audio_handle_guard) {
                                                                // Calculate duration from MP3 size (~48kbps = 6000 bytes/sec)
                                                                let duration_secs = (mp3_bytes.len() as f64 / 6000.0).ceil() as u64 + 1;
                                                                sink.append(source);
                                                                let mut tts_guard = handle.tts_sink.lock().unwrap();
                                                                *tts_guard = Some(sink);
                                                                drop(tts_guard);
                                                                drop(audio_handle_guard);

                                                                // Transition to Speaking state — keep window visible
                                                                {
                                                                    let state_lock = stt_app_handle.state::<AppState>();
                                                                    let mut s = state_lock.state.lock().unwrap();
                                                                    *s = OrbState::Speaking;
                                                                }
                                                                stt_app_handle.emit("orb-state-change", OrbState::Speaking).unwrap();

                                                                // Send word timings to frontend for text sync
                                                                if let Some(words) = json.get("words") {
                                                                    let text = json["text"].as_str().unwrap_or("");
                                                                    let _ = stt_app_handle.emit("tts-words", serde_json::json!({
                                                                        "text": text,
                                                                        "words": words,
                                                                        "duration": duration_secs,
                                                                    }));
                                                                }

                // Show window if hidden
                if let Some(window) = stt_app_handle.get_webview_window("main") {
                    let hwnd = window.hwnd().unwrap();
                    unsafe {
                        let _ = ShowWindow(HWND(hwnd.0), SW_SHOWNA);
                    }
                    refresh_window_chrome(HWND(hwnd.0), true);
                }

                                                                let h = stt_app_handle.clone();
                                                                tauri::async_runtime::spawn(async move {
                                                                    tokio::time::sleep(std::time::Duration::from_secs(duration_secs)).await;
                                                                    let state_lock = h.state::<AppState>();
                                                                    let mut tts_guard = state_lock.tts_sink.lock().unwrap();
                                                                    if let Some(sink) = tts_guard.take() {
                                                                        sink.stop();
                                                                    }
                                                                    // Transition Speaking → Idle, hide window
                                                                    let mut s = state_lock.state.lock().unwrap();
                                                                    if matches!(*s, OrbState::Speaking) {
                                                                        *s = OrbState::Idle;
                                                                        h.emit("orb-state-change", OrbState::Idle).unwrap();
                                                                        if let Some(window) = h.get_webview_window("main") {
                                                                            let _ = window.hide();
                                                                        }
                                                                    }
                                                                });
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            _ => {}
                                        }
                                    }
                                }
                            }
                            CommandEvent::Stderr(line_bytes) => {
                                let line = String::from_utf8_lossy(&line_bytes);
                                eprintln!("STT Error: {}", line);
                            }
                            CommandEvent::Terminated(payload) => {
                                eprintln!(
                                    "STT process terminated with code {:?}. Restarting in 3s...",
                                    payload.code
                                );
                                break; // Exit the while loop to restart
                            }
                            _ => {}
                        }
                    }

                    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                }
            });

            // Start the local LLM server if local AI mode is configured
            {
                let store = app_handle.store("settings.json");
                let ai_mode = store.as_ref().ok()
                    .and_then(|s| s.get("ai_mode"))
                    .and_then(|v| v.as_str().map(String::from))
                    .unwrap_or_else(|| "off".to_string());
                let model_path = store.as_ref().ok()
                    .and_then(|s| s.get("ai_local_model"))
                    .and_then(|v| v.as_str().map(String::from))
                    .unwrap_or_default();

                if ai_mode == "local"
                    && !model_path.is_empty()
                    && std::path::Path::new(&model_path).exists()
                {
                    if let Err(e) = spawn_llama_server(&app_handle, &model_path) {
                        eprintln!("llama-server startup failed: {}", e);
                    }
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            toggle_playback, 
            media_command, 
            register_shortcut, 
            set_audio_feedback, 
            set_sensitive_protection,
            set_tts_enabled,
            set_tts_voice,
            preview_voice,
            set_ai_mode,
            set_ai_local_model,
            set_ai_cloud,
            set_personality,
            set_followup_enabled,
            set_wake_sensitivity,
            gpu_status,
            set_gpu_accel,
            install_gpu_runtime,
            list_audio_devices,
            set_input_device,
            set_output_device,
            download_file,
            file_exists,
            delete_file,
            get_app_version,
            check_for_update,
            install_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
