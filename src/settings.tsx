import React, { useState, useEffect, useCallback, useRef } from "react";
import ReactDOM from "react-dom/client";
import { isEnabled, enable, disable } from "@tauri-apps/plugin-autostart";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { invoke } from "@tauri-apps/api/core";
import { emit } from "@tauri-apps/api/event";
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
  Brain,
  ChevronDown,
  Download,
  Check,
} from "lucide-react";
import "./index.css";

const appWindow = getCurrentWindow();

type Tab = "general" | "commands" | "voice" | "ai" | "activation" | "about";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "general", label: "General", icon: <Rocket className="w-4 h-4" /> },
  { id: "commands", label: "Commands", icon: <Shield className="w-4 h-4" /> },
  { id: "voice", label: "Voice", icon: <Volume2 className="w-4 h-4" /> },
  { id: "ai", label: "AI", icon: <Brain className="w-4 h-4" /> },
  { id: "activation", label: "Activation", icon: <Keyboard className="w-4 h-4" /> },
  { id: "about", label: "About", icon: <Info className="w-4 h-4" /> },
];

const MODELS = [
  {
    id: "qwen2.5-0.5b",
    name: "Qwen 2.5 0.5B",
    size: "~400 MB",
    desc: "Fastest, lowest RAM. Good for simple tasks.",
    url: "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
    filename: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
  },
  {
    id: "qwen2.5-1.5b",
    name: "Qwen 2.5 1.5B",
    size: "~1.1 GB",
    desc: "Best balance of speed and capability.",
    url: "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf",
  },
  {
    id: "llama-3.2-1b",
    name: "Llama 3.2 1B",
    size: "~800 MB",
    desc: "Meta's small model. Fast inference.",
    url: "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    filename: "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
  },
];

function Dropdown({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value)?.label ?? value;

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 hover:border-white/15 transition-colors cursor-pointer min-w-[120px] justify-between"
      >
        <span className="truncate">{selected}</span>
        <ChevronDown className={`w-3 h-3 text-white/30 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-full bg-[#1c1c1e] border border-white/[0.08] rounded-lg shadow-xl z-50 py-1 overflow-hidden">
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              className={`w-full px-2.5 py-1.5 text-left text-[12px] transition-colors cursor-pointer flex items-center justify-between ${
                opt.value === value
                  ? "bg-sky-500/20 text-sky-400"
                  : "text-white/60 hover:bg-white/[0.06] hover:text-white/80"
              }`}
            >
              <span className="truncate">{opt.label}</span>
              {opt.value === value && <Check className="w-3 h-3 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
  const [transcriptionEnabled, setTranscriptionEnabled] = useState(true);
  const [ttsVoice, setTtsVoice] = useState("en-US-JennyNeural");
  const [aiMode, setAiMode] = useState<"off" | "local" | "cloud">("off");
  const [aiLocalModel, setAiLocalModel] = useState("");
  const [aiCloudApiKey, setAiCloudApiKey] = useState("");
  const [aiCloudBaseUrl, setAiCloudBaseUrl] = useState("https://api.openai.com/v1");
  const [aiCloudCustomUrl, setAiCloudCustomUrl] = useState("");
  const [aiCloudModel, setAiCloudModel] = useState("gpt-4o-mini");
  const [hotkey, setHotkey] = useState("Ctrl+Shift+R");
  const [isRecording, setIsRecording] = useState(false);
  const [appVersion, setAppVersion] = useState("0.1.0");
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<{ version: string; body: string } | null>(null);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [downloadingModel, setDownloadingModel] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const downloadAbortRef = useRef<AbortController | null>(null);
  const [modelDir, setModelDir] = useState<string>("");
  const [installedModels, setInstalledModels] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setAutostart(await isEnabled());
        const store = await load("settings.json", { autoSave: true, defaults: {} });
        const savedHotkey = await store.get<string>("activation_hotkey");
        if (savedHotkey) setHotkey(savedHotkey);
        const savedAudioCues = await store.get<boolean>("audio_feedback");
        if (typeof savedAudioCues === "boolean") setAudioCues(savedAudioCues);
        const savedProtection = await store.get<boolean>("sensitive_protection");
        setSensitiveProtection(typeof savedProtection === "boolean" ? savedProtection : true);
        const savedTts = await store.get<boolean>("tts_enabled");
        setTtsEnabled(typeof savedTts === "boolean" ? savedTts : true);
        const savedTranscription = await store.get<boolean>("transcription_enabled");
        setTranscriptionEnabled(typeof savedTranscription === "boolean" ? savedTranscription : true);
        const savedVoice = await store.get<string>("tts_voice");
        if (savedVoice) setTtsVoice(savedVoice);
        const savedAiMode = await store.get<string>("ai_mode");
        if (savedAiMode === "local" || savedAiMode === "cloud") setAiMode(savedAiMode);
        const savedAiModel = await store.get<string>("ai_local_model");
        if (savedAiModel) setAiLocalModel(savedAiModel);
        const savedAiKey = await store.get<string>("ai_cloud_api_key");
        if (savedAiKey) setAiCloudApiKey(savedAiKey);
        const savedAiUrl = await store.get<string>("ai_cloud_base_url");
        if (savedAiUrl) setAiCloudBaseUrl(savedAiUrl);
        const savedAiModelId = await store.get<string>("ai_cloud_model");
        if (savedAiModelId) setAiCloudModel(savedAiModelId);
        setAppVersion(await invoke<string>("get_app_version"));
        const { appDataDir } = await import("@tauri-apps/api/path");
        const dir = `${await appDataDir()}\\models`;
        setModelDir(dir);
        // Check which quick download models exist on disk
        const checks: Record<string, boolean> = {};
        for (const m of MODELS) {
          checks[m.id] = await invoke<boolean>("file_exists", { path: `${dir}\\${m.filename}` });
        }
        setInstalledModels(checks);
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
    try { await appWindow.close(); } catch { await appWindow.hide(); }
  };

  const startRecording = () => setIsRecording(true);

  const stopRecording = useCallback(async (newHotkey: string) => {
    setIsRecording(false);
    if (!newHotkey) return;
    setHotkey(newHotkey);
    const store = await load("settings.json");
    await store.set("activation_hotkey", newHotkey);
    try { await invoke("register_shortcut", { shortcutStr: newHotkey }); }
    catch { alert("Invalid shortcut combination or already in use."); }
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

  const handleCheckForUpdates = async (isAuto: boolean | React.MouseEvent = false) => {
    const auto = isAuto === true;
    setCheckingUpdate(true);
    if (!auto) setUpdateStatus(null);
    setUpdateInfo(null);
    try {
      const res = await invoke<{ available: boolean; version: string | null; body: string | null }>("check_for_update");
      if (res.available && res.version) {
        setUpdateInfo({ version: res.version, body: res.body || "No release notes provided." });
      } else if (!auto) {
        setUpdateStatus("Jen is up to date!");
        setTimeout(() => setUpdateStatus(null), 3000);
      }
    } catch {
      if (!auto) {
        setUpdateStatus("Failed to check for updates");
        setTimeout(() => setUpdateStatus(null), 4000);
      }
    } finally { setCheckingUpdate(false); }
  };

  const handleInstallUpdate = async () => {
    setInstallingUpdate(true);
    setUpdateStatus("Downloading and installing update...");
    try { await invoke("install_update"); }
    catch {
      setUpdateStatus("Failed to install update");
      setInstallingUpdate(false);
      setTimeout(() => setUpdateStatus(null), 4000);
    }
  };

  useEffect(() => {
    let unlisten: (() => void) | null = null;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<{ path: string; progress: number }>("download-progress", (event) => {
        // Only update if it's for the model we're currently downloading
        if (downloadingModel) {
          const model = MODELS.find(m => m.id === downloadingModel);
          if (model && event.payload.path.includes(model.filename)) {
            setDownloadProgress(event.payload.progress);
          }
        }
      }).then((fn) => { unlisten = fn; });
    });
    return () => { unlisten?.(); };
  }, [downloadingModel]);

  const handleCancelDownload = () => {
    downloadAbortRef.current?.abort();
    downloadAbortRef.current = null;
    setDownloadingModel(null);
    setDownloadProgress(0);
  };

  const handleDownloadModel = async (model: typeof MODELS[0]) => {
    // Prevent double download
    if (downloadingModel) return;

    setDownloadingModel(model.id);
    setDownloadProgress(0);
    const controller = new AbortController();
    downloadAbortRef.current = controller;

    try {
      const { appDataDir } = await import("@tauri-apps/api/path");
      const dir = await appDataDir();
      const path = `${dir}\\models\\${model.filename}`;

      await invoke("download_file", { request: { url: model.url, path } });

      if (controller.signal.aborted) return;

      // Auto-switch to downloaded model
      setAiLocalModel(path);
      setAiMode("local");
      await updateSetting("ai_local_model", path, "set_ai_local_model", { modelPath: path });
      await updateSetting("ai_mode", "local", "set_ai_mode", { mode: "local" });
      setInstalledModels(prev => ({ ...prev, [model.id]: true }));
      setDownloadingModel(null);
      setDownloadProgress(0);
    } catch (e) {
      if (controller.signal.aborted) return;
      console.error("Download failed:", e);
      setDownloadingModel(null);
      setDownloadProgress(0);
      setUpdateStatus("Download failed — check your connection");
      setTimeout(() => setUpdateStatus(null), 4000);
    } finally {
      downloadAbortRef.current = null;
    }
  };

  useEffect(() => { handleCheckForUpdates(true); }, []);

  return (
    <div className="h-screen w-screen bg-[#111113] text-white/90 font-sans flex flex-col overflow-hidden border border-white/[0.06] rounded-xl">
      {/* Titlebar */}
      <div
        className="h-11 flex items-center justify-between px-4 shrink-0 relative select-none border-b border-white/[0.06]"
        data-tauri-drag-region
        onMouseDown={(e) => { if (e.target === e.currentTarget) appWindow.startDragging(); }}
      >
        <div className="flex items-center gap-2 pointer-events-none z-10">
          <Settings className="w-3.5 h-3.5 text-white/30" />
          <span className="text-[11px] font-medium text-white/40 tracking-wide">Settings</span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); handleClose(); }}
          className="p-1 hover:bg-white/10 rounded-md transition-colors text-white/30 hover:text-white/60 z-50 relative cursor-pointer no-drag"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Body */}
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
            <div className="px-2.5 text-[10px] text-white/20">v{appVersion}</div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 custom-scrollbar">
          {activeTab === "general" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">General</h2>
              <Row icon={<Rocket className="w-[15px] h-[15px]" />} label="Launch on Startup" description="Start Jen when Windows begins">
                <Toggle checked={autostart} onChange={async (v) => { setAutostart(v); v ? await enable() : await disable(); }} />
              </Row>
              <Row icon={<Bell className="w-[15px] h-[15px]" />} label="Audio Feedback" description="Play sounds when Jen hears you">
                <Toggle checked={audioCues} onChange={(v) => { setAudioCues(v); updateSetting("audio_feedback", v, "set_audio_feedback"); }} />
              </Row>
            </div>
          )}

          {activeTab === "commands" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">Commands</h2>
              <Row icon={<Shield className="w-[15px] h-[15px]" />} label="Sensitive Command Protection" description="Block power commands like shutdown, restart, sleep">
                <Toggle checked={sensitiveProtection} onChange={(v) => { setSensitiveProtection(v); updateSetting("sensitive_protection", v, "set_sensitive_protection"); }} />
              </Row>
            </div>
          )}

          {activeTab === "voice" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">Voice</h2>
              <Row icon={<Volume2 className="w-[15px] h-[15px]" />} label="Voice Responses" description="Jen speaks responses aloud">
                <Toggle checked={ttsEnabled} onChange={(v) => { setTtsEnabled(v); updateSetting("tts_enabled", v, "set_tts_enabled"); }} />
              </Row>
              {ttsEnabled && (
                <div className="mt-3 pl-[27px]">
                  <div className="flex items-center gap-2">
                    <Dropdown
                      value={ttsVoice}
                      options={[
                        { value: "en-US-JennyNeural", label: "Jenny (US, Female)" },
                        { value: "en-US-AriaNeural", label: "Aria (US, Female)" },
                        { value: "en-US-GuyNeural", label: "Guy (US, Male)" },
                        { value: "en-GB-SoniaNeural", label: "Sonia (UK, Female)" },
                        { value: "en-GB-RyanNeural", label: "Ryan (UK, Male)" },
                        { value: "en-AU-NatashaNeural", label: "Natasha (AU, Female)" },
                        { value: "en-IN-NeerjaNeural", label: "Neerja (IN, Female)" },
                      ]}
                      onChange={(v) => { setTtsVoice(v); updateSetting("tts_voice", v, "set_tts_voice", { voice: v }); }}
                    />
                    <button
                      onClick={() => invoke("preview_voice", { voice: ttsVoice })}
                      className="p-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-white/30 hover:text-white/70 hover:bg-white/[0.08] transition-colors cursor-pointer"
                      title="Preview voice"
                    >
                      <Play className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              )}
              <Row icon={<Volume2 className="w-[15px] h-[15px]" />} label="Live Transcription" description="Show words as Jen speaks">
                <Toggle checked={transcriptionEnabled} onChange={(v) => { setTranscriptionEnabled(v); updateSetting("transcription_enabled", v); emit("transcription-changed", v); }} />
              </Row>
            </div>
          )}

          {activeTab === "ai" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">AI</h2>
              <Row icon={<Brain className="w-[15px] h-[15px]" />} label="AI Mode" description="Use AI for questions and complex tasks">
                <Dropdown
                  value={aiMode}
                  options={[
                    { value: "off", label: "Off" },
                    { value: "local", label: "Local (llama.cpp)" },
                    { value: "cloud", label: "Cloud API" },
                  ]}
                  onChange={(v) => { const val = v as "off" | "local" | "cloud"; setAiMode(val); updateSetting("ai_mode", val, "set_ai_mode", { mode: val }); }}
                />
              </Row>

              {aiMode === "local" && (
                <div className="mt-3 pl-[27px] space-y-4">
                  <div>
                    <label className="text-[11px] text-white/40 mb-2 block">Quick Download</label>
                    <div className="space-y-2">
                      {MODELS.map((model) => {
                        const isDownloading = downloadingModel === model.id;
                        const isInstalled = installedModels[model.id] ?? false;
                        const quickPath = `${modelDir}\\${model.filename}`;
                        const isActive = isInstalled && aiMode === "local" && aiLocalModel === quickPath;

                        const handleUse = async () => {
                          setAiLocalModel(quickPath);
                          setAiMode("local");
                          await updateSetting("ai_local_model", quickPath, "set_ai_local_model", { modelPath: quickPath });
                          await updateSetting("ai_mode", "local", "set_ai_mode", { mode: "local" });
                        };

                        const handleDelete = async (e: React.MouseEvent) => {
                          e.stopPropagation();
                          try {
                            await invoke("delete_file", { path: quickPath });
                            setInstalledModels(prev => ({ ...prev, [model.id]: false }));
                            if (isActive) {
                              setAiLocalModel("");
                              await updateSetting("ai_local_model", "", "set_ai_local_model", { modelPath: "" });
                            }
                          } catch (err) {
                            console.error("Delete failed:", err);
                          }
                        };

                        return (
                          <div key={model.id} className="bg-white/[0.02] border border-white/[0.05] rounded-lg px-3 py-2">
                            <div className="flex items-center justify-between">
                              <div className="min-w-0">
                                <p className="text-[12px] text-white/70 font-medium flex items-center gap-1.5">
                                  {model.name}
                                  {isActive && <span className="text-[9px] text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded-full">Active</span>}
                                </p>
                                <p className="text-[10px] text-white/30 mt-0.5">{model.size} — {model.desc}</p>
                              </div>
                              {isDownloading ? (
                                <button
                                  onClick={handleCancelDownload}
                                  className="ml-3 px-2.5 py-1 rounded-md bg-red-500/15 border border-red-500/20 text-[11px] text-red-400 hover:bg-red-500/25 transition-colors cursor-pointer whitespace-nowrap flex items-center gap-1.5 shrink-0"
                                >
                                  <X className="w-3 h-3" /> Cancel
                                </button>
                              ) : isInstalled ? (
                                <div className="flex items-center gap-1.5 ml-3 shrink-0">
                                  <button
                                    onClick={handleUse}
                                    disabled={isActive}
                                    className={`px-2.5 py-1 rounded-md text-[11px] transition-colors cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                                      isActive
                                        ? "bg-emerald-500/15 border border-emerald-500/20 text-emerald-400 opacity-60 cursor-default"
                                        : "bg-sky-500/15 border border-sky-500/20 text-sky-400 hover:bg-sky-500/25"
                                    }`}
                                  >
                                    {isActive ? <><Check className="w-3 h-3" /> Using</> : <><Play className="w-3 h-3" /> Use</>}
                                  </button>
                                  {!isActive && (
                                    <button
                                      onClick={handleDelete}
                                      className="px-1.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.06] text-white/30 hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer"
                                      title="Delete model"
                                    >
                                      <X className="w-3 h-3" />
                                    </button>
                                  )}
                                </div>
                              ) : (
                                <button
                                  onClick={() => handleDownloadModel(model)}
                                  disabled={downloadingModel !== null}
                                  className="ml-3 px-2.5 py-1 rounded-md bg-sky-500/15 border border-sky-500/20 text-[11px] text-sky-400 hover:bg-sky-500/25 transition-colors cursor-pointer disabled:opacity-40 whitespace-nowrap flex items-center gap-1.5 shrink-0"
                                >
                                  <Download className="w-3 h-3" /> Download
                                </button>
                              )}
                            </div>
                            {isDownloading && (
                              <div className="mt-2 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-sky-500 rounded-full transition-all duration-300"
                                  style={{ width: `${downloadProgress}%` }}
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="border-t border-white/[0.05] pt-3">
                    <label className="text-[11px] text-white/40 mb-1.5 block">Custom Model</label>
                    <p className="text-[10px] text-white/25 mb-2">Load any .gguf model from your computer</p>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={aiLocalModel}
                        onChange={(e) => setAiLocalModel(e.target.value)}
                        onBlur={() => updateSetting("ai_local_model", aiLocalModel, "set_ai_local_model", { modelPath: aiLocalModel })}
                        placeholder="Path to .gguf file"
                        className="flex-1 px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 placeholder:text-white/20 outline-none focus:border-white/15 transition-colors"
                      />
                      <button
                        onClick={async () => {
                          const { open } = await import("@tauri-apps/plugin-dialog");
                          const file = await open({
                            multiple: false,
                            filters: [{ name: "GGUF Model", extensions: ["gguf"] }],
                          });
                          if (file) {
                            const path = typeof file === "string" ? file : file;
                            setAiLocalModel(path);
                            updateSetting("ai_local_model", path, "set_ai_local_model", { modelPath: path });
                          }
                        }}
                        className="px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/50 hover:text-white/70 hover:border-white/10 transition-colors cursor-pointer whitespace-nowrap"
                      >
                        Browse
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {aiMode === "cloud" && (
                <div className="mt-3 pl-[27px] space-y-3">
                  <div>
                    <label className="text-[11px] text-white/40 mb-1 block">API Key</label>
                    <input
                      type="password"
                      value={aiCloudApiKey}
                      onChange={(e) => setAiCloudApiKey(e.target.value)}
                      onBlur={() => {
                        const finalUrl = aiCloudBaseUrl === "custom" ? aiCloudCustomUrl : aiCloudBaseUrl;
                        updateSetting("ai_cloud_api_key", aiCloudApiKey, "set_ai_cloud", { apiKey: aiCloudApiKey, baseUrl: finalUrl, model: aiCloudModel });
                      }}
                      placeholder="sk-..."
                      className="w-full px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 placeholder:text-white/20 outline-none focus:border-white/15 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-white/40 mb-1 block">Provider</label>
                    <Dropdown
                      value={aiCloudBaseUrl}
                      options={[
                        { value: "https://api.openai.com/v1", label: "OpenAI" },
                        { value: "https://api.groq.com/openai/v1", label: "Groq" },
                        { value: "https://api.together.xyz/v1", label: "Together" },
                        { value: "custom", label: "Custom" },
                      ]}
                      onChange={(v) => {
                        setAiCloudBaseUrl(v);
                        if (v.includes("openai")) setAiCloudModel("gpt-4o-mini");
                        else if (v.includes("groq")) setAiCloudModel("llama-3.1-8b-instant");
                        else if (v.includes("together")) setAiCloudModel("meta-llama/Llama-3-8b-chat-hf");
                      }}
                    />
                  </div>
                  {aiCloudBaseUrl === "custom" && (
                    <div>
                      <label className="text-[11px] text-white/40 mb-1 block">Base URL</label>
                      <input
                        type="text"
                        value={aiCloudCustomUrl}
                        onChange={(e) => setAiCloudCustomUrl(e.target.value)}
                        onBlur={() => updateSetting("ai_cloud_base_url", aiCloudCustomUrl, "set_ai_cloud", { apiKey: aiCloudApiKey, baseUrl: aiCloudCustomUrl, model: aiCloudModel })}
                        placeholder="https://api.example.com/v1"
                        className="w-full px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 placeholder:text-white/20 outline-none focus:border-white/15 transition-colors"
                      />
                    </div>
                  )}
                  <div>
                    <label className="text-[11px] text-white/40 mb-1 block">Model</label>
                    <input
                      type="text"
                      value={aiCloudModel}
                      onChange={(e) => setAiCloudModel(e.target.value)}
                      onBlur={() => {
                        const finalUrl = aiCloudBaseUrl === "custom" ? aiCloudCustomUrl : aiCloudBaseUrl;
                        updateSetting("ai_cloud_model", aiCloudModel, "set_ai_cloud", { apiKey: aiCloudApiKey, baseUrl: finalUrl, model: aiCloudModel });
                      }}
                      placeholder="gpt-4o-mini"
                      className="w-full px-2.5 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.06] text-[12px] text-white/70 placeholder:text-white/20 outline-none focus:border-white/15 transition-colors"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "activation" && (
            <div className="space-y-1">
              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">Activation</h2>
              <Row icon={<Keyboard className="w-[15px] h-[15px]" />} label="Activation Hotkey" description="Press to manually trigger Jen">
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
              <Row icon={<RotateCcw className="w-[15px] h-[15px]" />} label="Reset Hotkey" description="Revert to Ctrl+Shift+R">
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

              <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">About</h2>
              <Row icon={<RefreshCw className={`w-[15px] h-[15px] ${checkingUpdate ? "animate-spin" : ""}`} />} label="Software Update" description={`Current version: ${appVersion}`}>
                <button onClick={handleCheckForUpdates} disabled={checkingUpdate || installingUpdate} className="px-2.5 py-1 rounded-lg border border-white/[0.06] bg-white/[0.04] text-[11px] text-white/50 hover:text-white/70 hover:border-white/10 transition-colors disabled:opacity-40 cursor-pointer">
                  {checkingUpdate ? "Checking..." : "Check"}
                </button>
              </Row>

              {updateStatus && (
                <div className="ml-[27px] mt-2 text-[11px] text-sky-400/80 bg-sky-500/10 px-3 py-1.5 rounded-lg">{updateStatus}</div>
              )}

              {updateInfo && (
                <div className="ml-[27px] mt-2 bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 space-y-2.5">
                  <p className="text-[12px] text-white/70 font-medium">Update Available: v{updateInfo.version}</p>
                  <button onClick={handleInstallUpdate} disabled={installingUpdate} className="w-full py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-[11px] font-medium transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer">
                    {installingUpdate ? (<><RefreshCw className="w-3 h-3 animate-spin" /> Installing...</>) : (<><ArrowUpCircle className="w-3 h-3" /> Install and Restart</>)}
                  </button>
                </div>
              )}

              <div className="mt-6 pt-4 border-t border-white/[0.06]">
                <h2 className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3">Changelog</h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-[11px] font-medium text-white/50">v0.1.0</p>
                    <ul className="mt-1 space-y-1">
                      {[
                        "Voice responses with Edge TTS (Jenny voice)",
                        "Greeting on wake word detection",
                        "Voice selector with 7 English voices",
                        "AI support (local llama.cpp + cloud APIs)",
                        "Voice dictation (type text by speaking)",
                        "Button press commands (Enter, Tab, Escape, etc.)",
                        "Noise-resistant wake word with RMS energy gating",
                        "Auto-update check on launch",
                        "Redesigned settings with sidebar navigation",
                      ].map((item) => (
                        <li key={item} className="text-[11px] text-white/30 flex gap-2">
                          <span className="text-sky-400/60 shrink-0">+</span>
                          <span>{item}</span>
                        </li>
                      ))}
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
