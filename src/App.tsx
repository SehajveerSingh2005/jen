import { useState, useEffect, useMemo, useRef } from "react";
import { Orb, AgentState } from "./components/Orb";
import { listen } from "@tauri-apps/api/event";
import { load } from "@tauri-apps/plugin-store";
import { motion, AnimatePresence } from "framer-motion";

type AppOrbState = "idle" | "startup" | "listening" | "processing" | "success" | "error" | "recording" | "speaking";

interface WordTiming {
  text: string;
  offset: number;
  duration: number;
}

function App() {
  const [state, setState] = useState<AppOrbState>("idle");
  const [visibleWords, setVisibleWords] = useState<string[]>([]);
  const [fading, setFading] = useState(false);
  const [transcriptionEnabled, setTranscriptionEnabled] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const loadSetting = async () => {
      try {
        const store = await load("settings.json", { autoSave: true, defaults: {} });
        const val = await store.get<boolean>("transcription_enabled");
        setTranscriptionEnabled(typeof val === "boolean" ? val : true);
      } catch {}
    };
    loadSetting();
  }, []);

  useEffect(() => {
    const unlisten = listen<boolean>("transcription-changed", (event) => {
      setTranscriptionEnabled(event.payload);
    });
    return () => { unlisten.then((f) => f()); };
  }, []);

  useEffect(() => {
    const unlisten = listen<AppOrbState>("orb-state-change", (event) => {
      setState(event.payload);
    });
    return () => { unlisten.then((f) => f()); };
  }, []);

  useEffect(() => {
    const unlisten = listen<{ text: string; words: WordTiming[]; duration: number }>("tts-words", (event) => {
      const { words } = event.payload;

      timerRef.current.forEach(clearTimeout);
      timerRef.current = [];
      setVisibleWords([]);
      setFading(false);

      if (words.length === 0) {
        const t = setTimeout(() => setVisibleWords([event.payload.text]), 0);
        timerRef.current.push(t);
        return;
      }

      // Add one word at a time, sliding in
      words.forEach((word) => {
        const t = setTimeout(() => {
          setVisibleWords((prev) => [...prev, word.text]);
        }, word.offset * 1000);
        timerRef.current.push(t);
      });

      // After all words, fade out
      const lastWord = words[words.length - 1];
      const end = lastWord.offset + lastWord.duration;
      const fadeTimer = setTimeout(() => setFading(true), (end + 0.3) * 1000);
      timerRef.current.push(fadeTimer);

      const clearTimer = setTimeout(() => {
        setVisibleWords([]);
        setFading(false);
      }, (end + 1.5) * 1000);
      timerRef.current.push(clearTimer);
    });

    return () => {
      unlisten.then((f) => f());
      timerRef.current.forEach(clearTimeout);
      timerRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (state !== "idle" && state !== "speaking" && state !== "success") {
      timerRef.current.forEach(clearTimeout);
      timerRef.current = [];
      setVisibleWords([]);
      setFading(false);
    }
  }, [state]);

  useEffect(() => {
    if (state !== "idle") {
      const t1 = setTimeout(() => window.dispatchEvent(new Event("resize")), 50);
      const t2 = setTimeout(() => window.dispatchEvent(new Event("resize")), 360);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, [state]);

  const orbProps = useMemo(() => {
    const defaultColors: [string, string] = ["#f8fafc", "#94a3b8"];
    switch (state) {
      case "startup":
        return { agentState: "thinking" as AgentState, colors: defaultColors };
      case "listening":
      case "recording":
        return { agentState: "listening" as AgentState, colors: ["#bae6fd", "#38bdf8"] as [string, string] };
      case "processing":
        return { agentState: "thinking" as AgentState, colors: ["#f3e8ff", "#a855f7"] as [string, string] };
      case "success":
        return { agentState: "talking" as AgentState, colors: ["#ecfdf5", "#10b981"] as [string, string] };
      case "speaking":
        return { agentState: "talking" as AgentState, colors: ["#fefce8", "#eab308"] as [string, string] };
      case "error":
        return { agentState: "thinking" as AgentState, colors: ["#fef2f2", "#ef4444"] as [string, string] };
      default:
        return { agentState: "listening" as AgentState, colors: defaultColors };
    }
  }, [state]);

  const hasWords = visibleWords.length > 0 && transcriptionEnabled;

  return (
    <main className="flex flex-col items-center justify-end w-screen h-screen bg-transparent overflow-visible select-none pb-2">
      {/* Accumulating word text */}
      <div className="mb-0 flex items-end justify-center w-full px-1">
        <AnimatePresence>
          {hasWords && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: fading ? 0 : 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="flex flex-wrap items-end justify-center gap-x-[6px] gap-y-1 w-full max-w-[300px]"
              style={{ maskImage: "linear-gradient(to bottom, transparent 0%, black 20%)", WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 20%)" }}
            >
              {visibleWords.map((word, i) => (
                <motion.span
                  layout
                  key={`${i}-${word}`}
                  initial={{ opacity: 0, filter: "blur(4px)" }}
                  animate={{ opacity: 1, filter: "blur(0px)" }}
                  transition={{ layout: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }, opacity: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }, filter: { duration: 0.35 } }}
                  className="text-[18px] text-white font-medium drop-shadow-lg leading-tight"
                >
                  {word}
                </motion.span>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Orb */}
      <AnimatePresence mode="wait">
        {state !== "idle" && (
          <motion.div
            key="orb-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="w-48 h-48 overflow-visible flex items-center justify-center"
          >
            <Orb {...orbProps} className="w-48 h-48" />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

export default App;
