import React, { useState, useEffect, useCallback } from "react";
import ReactDOM from "react-dom/client";
import { isEnabled, enable, disable } from "@tauri-apps/plugin-autostart";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";
import { Settings as SettingsIcon, Bell, Rocket, X, Keyboard, RotateCcw, Shield, RefreshCw, ArrowUpCircle } from "lucide-react";
import "./index.css";


const appWindow = getCurrentWindow();

function SettingsApp() {
  const [autostart, setAutostart] = useState(false);
  const [audioCues, setAudioCues] = useState(true);
  const [sensitiveProtection, setSensitiveProtection] = useState(true);
  const [hotkey, setHotkey] = useState("Ctrl+Shift+R");
  const [isRecording, setIsRecording] = useState(false);
  const [appVersion, setAppVersion] = useState("0.1.0");
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<{ version: string; body: string } | null>(null);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const autostartEnabled = await isEnabled();
        setAutostart(autostartEnabled);

        const store = await load("settings.json", { autoSave: true, defaults: {} });
        const savedHotkey = await store.get<string>("activation_hotkey");
        if (savedHotkey) setHotkey(savedHotkey);

        const savedAudioCues = await store.get<boolean>("audio_feedback");
        if (typeof savedAudioCues === "boolean") {
          setAudioCues(savedAudioCues);
        }

        const savedProtection = await store.get<boolean>("sensitive_protection");
        setSensitiveProtection(typeof savedProtection === "boolean" ? savedProtection : true);

        const ver = await invoke<string>("get_app_version");
        setAppVersion(ver);
      } catch (e) {
        console.error("Failed to load settings:", e);
      }
    };

    loadSettings();
  }, []);

  const toggleAutostart = async () => {
    try {
      if (autostart) {
        await disable();
      } else {
        await enable();
      }
      setAutostart(!autostart);
    } catch (e) {
      console.error("Failed to toggle autostart:", e);
    }
  };

  const updateAudioCues = async (val: boolean) => {
    try {
      setAudioCues(val);
      const store = await load("settings.json");
      await store.set("audio_feedback", val);
      await invoke("set_audio_feedback", { enabled: val });
    } catch (e) {
      console.error("Failed to update audio cues:", e);
    }
  };

  const updateSensitiveProtection = async (val: boolean) => {
    try {
      setSensitiveProtection(val);
      const store = await load("settings.json");
      await store.set("sensitive_protection", val);
      await invoke("set_sensitive_protection", { enabled: val });
    } catch (e) {
      console.error("Failed to update sensitive protection:", e);
    }
  };

  const handleClose = async () => {
    try {
      console.log("Attempting to close settings window...");
      await appWindow.close();
    } catch (e) {
      console.error("Failed to close window via appWindow.close():", e);
      // Fallback: try to hide it
      await appWindow.hide();
    }
  };

  const startRecording = () => {
    setIsRecording(true);
  };

  const stopRecording = useCallback(async (newHotkey: string) => {
    setIsRecording(false);
    if (!newHotkey) return;

    setHotkey(newHotkey);
    
    // Save to store
    const store = await load("settings.json");
    await store.set("activation_hotkey", newHotkey);

    // Register in Rust
    try {
      await invoke("register_shortcut", { shortcutStr: newHotkey });
    } catch (e) {
      console.error("Failed to register shortcut:", e);
      alert("Invalid shortcut combination or already in use.");
    }
  }, []);

  useEffect(() => {
    if (!isRecording) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const keys: string[] = [];
      if (e.ctrlKey) keys.push("Ctrl");
      if (e.shiftKey) keys.push("Shift");
      if (e.altKey) keys.push("Alt");
      if (e.metaKey) keys.push("Command");

      const key = e.key.toUpperCase();
      if (!["CONTROL", "SHIFT", "ALT", "META", "OS"].includes(key)) {
        let finalKey = key;
        if (key === " ") finalKey = "Space";
        keys.push(finalKey);
        
        const combination = keys.join("+");
        stopRecording(combination);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRecording, stopRecording]);

  const handleCheckForUpdates = async (isAuto: boolean | React.MouseEvent = false) => {
    const auto = isAuto === true;
    setCheckingUpdate(true);
    if (!auto) {
      setUpdateStatus(null);
    }
    setUpdateInfo(null);
    try {
      const res = await invoke<{ available: boolean; version: string | null; body: string | null }>("check_for_update");
      if (res.available && res.version) {
        setUpdateInfo({
          version: res.version,
          body: res.body || "No release notes provided."
        });
      } else {
        if (!auto) {
          setUpdateStatus("Jen is up to date!");
          setTimeout(() => setUpdateStatus(null), 3000);
        }
      }
    } catch (e) {
      console.error("Check for update failed:", e);
      if (!auto) {
        setUpdateStatus("Failed to check for updates");
        setTimeout(() => setUpdateStatus(null), 4000);
      }
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleInstallUpdate = async () => {
    setInstallingUpdate(true);
    setUpdateStatus("Downloading and installing update...");
    try {
      await invoke("install_update");
    } catch (e) {
      console.error("Install update failed:", e);
      setUpdateStatus("Failed to install update");
      setInstallingUpdate(false);
      setTimeout(() => setUpdateStatus(null), 4000);
    }
  };

  useEffect(() => {
    // Automatically check for updates silently on settings mount
    handleCheckForUpdates(true);
  }, []);

  return (
    <div className="h-screen w-screen bg-[#0a0a0a] text-slate-200 font-sans flex flex-col selection:bg-sky-500/30 overflow-hidden border border-white/10 rounded-xl shadow-2xl">
      {/* Custom Titlebar */}
      <div className="h-10 flex items-center justify-between px-4 bg-slate-900/90 border-b border-white/5 shrink-0 relative select-none">
        {/* The actual draggable area - we use an absolute div that fills the space but stays behind the button */}
        <div 
          data-tauri-drag-region
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              appWindow.startDragging();
            }
          }}
          className="absolute inset-0 z-0 drag-region cursor-default"
        />
        
        <div className="flex items-center gap-2 pointer-events-none z-10">
          <SettingsIcon className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Jen Settings</span>
        </div>

        <button 
          onClick={(e) => {
            e.stopPropagation();
            handleClose();
          }}
          className="p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded-lg transition-colors text-slate-500 z-50 relative cursor-pointer no-drag"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
        {/* Header */}
        <header className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <SettingsIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white leading-tight">Preferences</h1>
            <p className="text-xs text-slate-500 tracking-wide font-medium">Customize your experience</p>
          </div>
        </header>

        <main className="space-y-6">
          {/* General Section */}
          <section className="space-y-3">
            <h2 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">General</h2>
            
            <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-4 space-y-4 backdrop-blur-sm">
              {/* Launch on Startup */}
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-sky-500/30">
                    <Rocket className="w-4 h-4 text-slate-400 group-hover:text-sky-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Launch on Startup</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">Start Jen when Windows begins</p>
                  </div>
                </div>
                <button 
                  onClick={toggleAutostart}
                  className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none ${autostart ? 'bg-sky-500' : 'bg-slate-700'}`}
                >
                  <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${autostart ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>

              {/* Audio Feedback */}
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-sky-500/30">
                    <Bell className="w-4 h-4 text-slate-400 group-hover:text-sky-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Audio Feedback</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">Play sounds when Jen hears you</p>
                  </div>
                </div>
                <button 
                  onClick={() => updateAudioCues(!audioCues)}
                  className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none ${audioCues ? 'bg-sky-500' : 'bg-slate-700'}`}
                >
                  <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${audioCues ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>
          </section>

          {/* Commands Section */}
          <section className="space-y-3">
            <h2 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Commands</h2>
            <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-4 backdrop-blur-sm">
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-amber-500/30">
                    <Shield className="w-4 h-4 text-slate-400 group-hover:text-amber-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Sensitive Command Protection</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">Block power commands (shutdown, restart, sleep…)</p>
                  </div>
                </div>
                <button
                  onClick={() => updateSensitiveProtection(!sensitiveProtection)}
                  className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none ${sensitiveProtection ? 'bg-amber-500' : 'bg-slate-700'}`}
                >
                  <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${sensitiveProtection ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>
          </section>

          {/* Activation Section */}
          <section className="space-y-3">
            <h2 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Activation</h2>
            <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-4 space-y-4 backdrop-blur-sm">
              {/* Manual Record Keybind */}
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-sky-500/30">
                    <Keyboard className="w-4 h-4 text-slate-400 group-hover:text-sky-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Activation Hotkey</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">Press to manually trigger Jen</p>
                  </div>
                </div>
                <button 
                  onClick={startRecording}
                  disabled={isRecording}
                  className={`px-3 py-1 rounded-lg border transition-all min-w-[100px] text-[10px] font-mono ${
                    isRecording 
                      ? 'bg-sky-500/20 border-sky-500 text-sky-400 animate-pulse' 
                      : 'bg-slate-800 border-white/5 text-sky-400 hover:border-sky-500/50'
                  }`}
                >
                  {isRecording ? "Press keys..." : hotkey}
                </button>
              </div>

              {/* Push to Talk / Toggle Record */}
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-sky-500/30">
                    <RotateCcw className="w-4 h-4 text-slate-400 group-hover:text-sky-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Reset Hotkey</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">Revert to Ctrl+Shift+R</p>
                  </div>
                </div>
                <button 
                  onClick={() => stopRecording("Ctrl+Shift+R")}
                  className="p-2 rounded-lg bg-slate-800 border border-white/5 text-slate-400 hover:text-sky-400 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </section>

          {/* Updates Section */}
          <section className="space-y-3">
            <h2 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Updates</h2>
            <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-4 space-y-4 backdrop-blur-sm">
              <div className="flex items-center justify-between group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5 transition-colors group-hover:border-sky-500/30">
                    <RefreshCw className={`w-4 h-4 text-slate-400 group-hover:text-sky-400 ${checkingUpdate ? 'animate-spin' : ''}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">Software Update</p>
                    <p className="text-[11px] text-slate-500 leading-none mt-1">
                      Current version: {appVersion}
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleCheckForUpdates}
                  disabled={checkingUpdate || installingUpdate}
                  className="px-3 py-1 rounded-lg border border-white/5 bg-slate-800 text-[10px] font-medium text-slate-200 hover:text-sky-400 hover:border-sky-500/50 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {checkingUpdate ? "Checking..." : "Check"}
                </button>
              </div>

              {updateStatus && (
                <div className="text-[11px] text-sky-400 bg-sky-500/10 px-3 py-2 rounded-xl border border-sky-500/20 text-center animate-fade-in">
                  {updateStatus}
                </div>
              )}

              {updateInfo && (
                <div className="bg-slate-800/50 border border-sky-500/20 rounded-xl p-3.5 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-semibold text-white">Update Available: v{updateInfo.version}</p>
                      <p className="text-[10px] text-slate-400 mt-1 max-h-[80px] overflow-y-auto font-mono custom-scrollbar pr-2 whitespace-pre-line">
                        {updateInfo.body}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleInstallUpdate}
                    disabled={installingUpdate}
                    className="w-full py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-[11px] font-semibold transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                  >
                    {installingUpdate ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Installing...
                      </>
                    ) : (
                      <>
                        <ArrowUpCircle className="w-3.5 h-3.5" />
                        Install and Restart
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* Footer info */}
          <footer className="pt-8 pb-4 flex flex-col items-center gap-2 border-t border-white/5">
             <div className="text-[10px] text-slate-600 font-medium tracking-wide">
               made with love by sehaz
             </div>
             <div className="text-[9px] text-slate-700 uppercase tracking-[0.2em] font-bold">
               Version {appVersion}
             </div>
          </footer>
        </main>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <SettingsApp />
  </React.StrictMode>
);
