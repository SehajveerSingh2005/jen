import React, { useState, useEffect, useCallback } from "react";
import ReactDOM from "react-dom/client";
import { isEnabled, enable, disable } from "@tauri-apps/plugin-autostart";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";
import {
  Settings,
  Rocket,
  Bell,
  Shield,
  Volume2,
  Keyboard,
  RotateCcw,
  RefreshCw,
  ArrowUpCircle,
  Play,
  Info,
  X,
} from "lucide-react";
import "./index.css";

const appWindow = getCurrentWindow();

type Tab = "general" | "commands" | "voice" | "activation" | "about";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "general", label: "General", icon: <Rocket className="w-4 h-4" /> },
  { id: "commands", label: "Commands", icon: <Shield className="w-4 h-4" /> },
  { id: "voice", label: "Voice", icon: <Volume2 className="w-4 h-4" /> },
  { id: "activation", label: "Activation", icon: <Keyboard className="w-4 h-4" /> },
  { id: "about", label: "About", icon: <Info className="w-4 h-4" /> },
];

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-[22px] w-[40px] shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none ${
        checked ? "bg-sky-500" : "bg-white/10"
      }`}
    >
      <span
        className={`inline-block h-[18px] w-[18px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
          checked ? "translate-x-[20px]" : "translate-x-[1px]"
        }`}
      />
    </button>
  );
}

function Row({
  icon,
  label,
  description,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-3">
        <div className="text-white/40">{icon}</div>
        <div>
          <p className="text-[13px] text-white/90">{label}</p>
          {description && (
            <p className="text-[11px] text-white/30 mt-0.5">{description}</p>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}

function SettingsApp() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [autostart, setAutostart] = useState(false);
  const [audioCues, setAudioCues] = useState(true);
  const [sensitiveProtection, setSensitiveProtection] = useState(true);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsVoice, setTtsVoice] = useState("en-US-JennyNeural");
  const [hotkey, setHotkey] = useState("Ctrl+Shift+R");
  const [isRecording, setIsRecording] = useState(false);
  const [appVersion, setAppVersion] = useState("0.1.0");
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<{
    version: string;
    body: string;
  } | null>(null);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setAutostart(await isEnabled());
        const store = await load("settings.json", {
          autoSave: true,
          defaults: {},
        });
        const savedHotkey = await store.get<string>("activation_hotkey");
        if (savedHotkey) setHotkey(savedHotkey);
        const savedAudioCues = await store.get<boolean>("audio_feedback");
        if (typeof savedAudioCues === "boolean") setAudioCues(savedAudioCues);
        const savedProtection = await store.get<boolean>(
          "sensitive_protection"
        );
        setSensitiveProtection(
          typeof savedProtection === "boolean" ? savedProtection : true
        );
        const savedTts = await store.get<boolean>("tts_enabled");
        setTtsEnabled(typeof savedTts === "boolean" ? savedTts : true);
        const savedVoice = await store.get<string>("tts_voice");
        if (savedVoice) setTtsVoice(savedVoice);
        setAppVersion(await invoke<string>("get_app_version"));
      } catch (e) {
        console.error("Failed to load settings:", e);
      }
    };
    loadSettings();
  }, []);

  const updateSetting = async (
    key: string,
    value: boolean | string,
    command?: string,
    commandArg?: Record<string, unknown>
  ) => {
    const store = await load("settings.json");
    await store.set(key, value);
    if (command) await invoke(command, commandArg ?? { enabled: value });
  };

  const handleClose = async () => {
    try {
      await appWindow.close();
    } catch {
      await appWindow.hide();
    }
  };

  const startRecording = () => setIsRecording(true);

  const stopRecording = useCallback(async (newHotkey: string) => {
    setIsRecording(false);
    if (!newHotkey) return;
    setHotkey(newHotkey);
    const store = await load("settings.json");
    await store.set("activation_hotkey", newHotkey);
    try {
      await invoke("register_shortcut", { shortcutStr: newHotkey });
    } catch {
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
        keys.push(key === " " ? "Space" : key);
        stopRecording(keys.join("+"));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRecording, stopRecording]);

  const handleCheckForUpdates = async (
    isAuto: boolean | React.MouseEvent = false
  ) => {
    const auto = isAuto === true;
    setCheckingUpdate(true);
    if (!auto) setUpdateStatus(null);
    setUpdateInfo(null);
    try {
      const res = await invoke<{
        available: boolean;
        version: string | null;
        body: string | null;
      }>("check_for_update");
      if (res.available && res.version) {
        setUpdateInfo({
          version: res.version,
          body: res.body || "No release notes provided.",
        });
      } else if (!auto) {
        setUpdateStatus("Jen is up to date!");
        setTimeout(() => setUpdateStatus(null), 3000);
      }
    } catch {
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
    } catch {
      setUpdateStatus("Failed to install update");
      setInstallingUpdate(false);
      setTimeout(() => setUpdateStatus(null), 4000);
    }
  };

  useEffect(() => {
    handleCheckForUpdates(true);
  }, []);

  return (
    <div className="h-screen w-screen bg-[#111113] text-white/90 font-sans flex flex-col overflow-hidden border border-white/[0.06] rounded-xl">
      {/* Titlebar */}
      <div
        className="h-11 flex items-center justify-between px-4 shrink-0 relative select-none border-b border-white/[0.06]"
        data-tauri-drag-region
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) appWindow.startDragging();
        }}
      >
        <div className="flex items-center gap-2 pointer-events-none z-10">
          <Settings className="w-3.5 h-3.5 text-white/30" />
          <span className="text-[11px] font-medium text-white/40 tracking-wide">
            Settings
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleClose();
          }}
          className="p-1 hover:bg-white/10 rounded-md transition-colors text-white/30 hover:text-white/60 z-50 relative cursor-pointer no-drag"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Body: Sidebar + Content */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar */}
        <div className="w-[140px] shrink-0 border-r border-white/[0.06] py-3 px-2 flex flex-col gap-0.5">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[12px] transition-colors cursor-pointer text-left w-full ${
                activeTab === tab.id
                  ? "bg-white/[0.08] text-white/90"
                  : "text-white/35 hover:text-white/60 hover:bg-white/[0.03]"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
          <div className="mt-auto pt-3 border-t border-white/[0.06]">
            <div className="px-2.5 text-[10px] text-white/20">
              v{appVersion}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 custom-scrollbar">
          {activeTab === "general" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                General
              </h2>
              <Row
                icon={<Rocket className="w-[15px] h-[15px]" />}
                label="Launch on Startup"
                description="Start Jen when Windows begins"
              >
                <Toggle
                  checked={autostart}
                  onChange={async (v) => {
                    setAutostart(v);
                    v ? await enable() : await disable();
                  }}
                />
              </Row>
              <Row
                icon={<Bell className="w-[15px] h-[15px]" />}
                label="Audio Feedback"
                description="Play sounds when Jen hears you"
              >
                <Toggle
                  checked={audioCues}
                  onChange={(v) => {
                    setAudioCues(v);
                    updateSetting("audio_feedback", v, "set_audio_feedback");
                  }}
                />
              </Row>
            </div>
          )}

          {activeTab === "commands" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                Commands
              </h2>
              <Row
                icon={<Shield className="w-[15px] h-[15px]" />}
                label="Sensitive Command Protection"
                description="Block power commands like shutdown, restart, sleep"
              >
                <Toggle
                  checked={sensitiveProtection}
                  onChange={(v) => {
                    setSensitiveProtection(v);
                    updateSetting(
                      "sensitive_protection",
                      v,
                      "set_sensitive_protection"
                    );
                  }}
                />
              </Row>
            </div>
          )}

          {activeTab === "voice" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                Voice
              </h2>
              <Row
                icon={<Volume2 className="w-[15px] h-[15px]" />}
                label="Voice Responses"
                description="Jen speaks responses aloud"
              >
                <Toggle
                  checked={ttsEnabled}
                  onChange={(v) => {
                    setTtsEnabled(v);
                    updateSetting("tts_enabled", v, "set_tts_enabled");
                  }}
                />
              </Row>

              {ttsEnabled && (
                <div className="mt-3 pl-[27px]">
                  <div className="flex items-center gap-2">
                    <select
                      value={ttsVoice}
                      onChange={(e) => {
                        setTtsVoice(e.target.value);
                        updateSetting(
                          "tts_voice",
                          e.target.value,
                          "set_tts_voice",
                          { voice: e.target.value }
                        );
                      }}
                      className="flex-1 px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 cursor-pointer outline-none focus:border-white/15 transition-colors appearance-none"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.3)' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
                        backgroundRepeat: "no-repeat",
                        backgroundPosition: "right 8px center",
                      }}
                    >
                      <option value="en-US-JennyNeural">
                        Jenny (US, Female)
                      </option>
                      <option value="en-US-AriaNeural">
                        Aria (US, Female)
                      </option>
                      <option value="en-US-GuyNeural">Guy (US, Male)</option>
                      <option value="en-GB-SoniaNeural">
                        Sonia (UK, Female)
                      </option>
                      <option value="en-GB-RyanNeural">
                        Ryan (UK, Male)
                      </option>
                      <option value="en-AU-NatashaNeural">
                        Natasha (AU, Female)
                      </option>
                      <option value="en-IN-NeerjaNeural">
                        Neerja (IN, Female)
                      </option>
                    </select>
                    <button
                      onClick={() =>
                        invoke("preview_voice", { voice: ttsVoice })
                      }
                      className="p-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-white/30 hover:text-white/70 hover:bg-white/[0.08] transition-colors cursor-pointer"
                      title="Preview voice"
                    >
                      <Play className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "activation" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                Activation
              </h2>
              <Row
                icon={<Keyboard className="w-[15px] h-[15px]" />}
                label="Activation Hotkey"
                description="Press to manually trigger Jen"
              >
                <button
                  onClick={startRecording}
                  disabled={isRecording}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all min-w-[90px] ${
                    isRecording
                      ? "bg-sky-500/15 border-sky-500/40 text-sky-400 animate-pulse"
                      : "bg-white/[0.04] border-white/[0.06] text-white/50 hover:text-white/70 hover:border-white/10"
                  }`}
                >
                  {isRecording ? "Press keys..." : hotkey}
                </button>
              </Row>
              <Row
                icon={<RotateCcw className="w-[15px] h-[15px]" />}
                label="Reset Hotkey"
                description="Revert to Ctrl+Shift+R"
              >
                <button
                  onClick={() => stopRecording("Ctrl+Shift+R")}
                  className="p-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-white/30 hover:text-white/70 transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </Row>
            </div>
          )}

          {activeTab === "about" && (
            <div className="space-y-1">
              <div className="flex flex-col items-center py-4 mb-2">
                <img src="/logo.png" alt="Jen" className="w-16 h-16 rounded-2xl" />
                <h1 className="text-lg font-semibold text-white/90 mt-3">Jen</h1>
                <p className="text-[11px] text-white/30 mt-0.5">Your desktop voice assistant</p>
              </div>

              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                About
              </h2>
              <Row
                icon={
                  <RefreshCw
                    className={`w-[15px] h-[15px] ${checkingUpdate ? "animate-spin" : ""}`}
                  />
                }
                label="Software Update"
                description={`Current version: ${appVersion}`}
              >
                <button
                  onClick={handleCheckForUpdates}
                  disabled={checkingUpdate || installingUpdate}
                  className="px-2.5 py-1 rounded-lg border border-white/[0.06] bg-white/[0.04] text-[11px] text-white/50 hover:text-white/70 hover:border-white/10 transition-colors disabled:opacity-40 cursor-pointer"
                >
                  {checkingUpdate ? "Checking..." : "Check"}
                </button>
              </Row>

              {updateStatus && (
                <div className="ml-[27px] mt-2 text-[11px] text-sky-400/80 bg-sky-500/10 px-3 py-1.5 rounded-lg">
                  {updateStatus}
                </div>
              )}

              {updateInfo && (
                <div className="ml-[27px] mt-2 bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 space-y-2.5">
                  <p className="text-[12px] text-white/70 font-medium">
                    Update Available: v{updateInfo.version}
                  </p>
                  <button
                    onClick={handleInstallUpdate}
                    disabled={installingUpdate}
                    className="w-full py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-[11px] font-medium transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                  >
                    {installingUpdate ? (
                      <>
                        <RefreshCw className="w-3 h-3 animate-spin" />
                        Installing...
                      </>
                    ) : (
                      <>
                        <ArrowUpCircle className="w-3 h-3" />
                        Install and Restart
                      </>
                    )}
                  </button>
                </div>
              )}

              <div className="mt-6 pt-4 border-t border-white/[0.06]">
                <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">
                  Changelog
                </h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-[11px] font-medium text-white/50">v0.1.0</p>
                    <ul className="mt-1 space-y-1">
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Voice responses with Edge TTS (Jenny voice)</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Greeting on wake word detection</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Voice selector with 7 English voices</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Voice dictation (type text by speaking)</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Button press commands (Enter, Tab, Escape, etc.)</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Noise-resistant wake word with RMS energy gating</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Auto-update check on launch</span>
                      </li>
                      <li className="text-[11px] text-white/30 flex gap-2">
                        <span className="text-sky-400/60 shrink-0">+</span>
                        <span>Redesigned settings with sidebar navigation</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <SettingsApp />
  </React.StrictMode>
);
