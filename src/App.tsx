import { useState, useEffect, useMemo } from "react";
import { Orb, AgentState } from "./components/Orb";
import { listen } from "@tauri-apps/api/event";
import { motion, AnimatePresence } from "framer-motion";

type AppOrbState = "idle" | "listening" | "processing" | "success" | "error" | "recording";

function App() {
  const [state, setState] = useState<AppOrbState>("idle");

  useEffect(() => {
    // Listen for state changes from Rust
    const unlisten = listen<AppOrbState>("orb-state-change", (event) => {
      setState(event.payload);
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  const orbProps = useMemo(() => {
    // Modern tech palette
    const defaultColors: [string, string] = ["#22d3ee", "#0ea5e9"]; // Cyan to Sky Blue (Tech Idle)
    
    switch (state) {
      case "listening":
      case "recording":
        return { 
          agentState: "listening" as AgentState, 
          colors: ["#3b82f6", "#2563eb"] as [string, string] // Deep Blue (Active Listening)
        };
      case "processing":
        return { 
          agentState: "thinking" as AgentState, 
          colors: ["#a855f7", "#7c3aed"] as [string, string] // Vibrant Purple (Thinking)
        };
      case "success":
        return { 
          agentState: "talking" as AgentState, 
          colors: ["#34d399", "#10b981"] as [string, string] // Emerald to Green (Success)
        };
      case "error":
        return { 
          agentState: "thinking" as AgentState, 
          colors: ["#f87171", "#dc2626"] as [string, string] // Red (Error)
        };
      default:
        return { 
          agentState: null as AgentState, 
          colors: defaultColors 
        };
    }
  }, [state]);

  return (
    <main className="flex items-center justify-center w-screen h-screen bg-transparent overflow-hidden select-none">
      <AnimatePresence mode="wait">
        {state !== "idle" && (
          <motion.div 
            key="orb-container"
            initial={{ opacity: 0, scale: 0.3, y: 100 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.3, y: 100 }}
            transition={{ 
              type: "spring", 
              stiffness: 500, 
              damping: 30,
              mass: 0.5
            }}
            className="w-32 h-32"
          >
            <Orb {...orbProps} />
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Dev helper to cycle states (remove in production) */}
      <div 
        className="fixed bottom-2 left-0 right-0 flex justify-center gap-2 opacity-0 hover:opacity-100 transition-opacity"
        onContextMenu={(e) => e.preventDefault()}
      >
        {(["idle", "listening", "processing", "success", "error"] as AppOrbState[]).map((s) => (
          <button
            key={s}
            onClick={() => setState(s)}
            className="px-2 py-1 text-[10px] bg-white/10 rounded hover:bg-white/20 border border-white/5"
          >
            {s}
          </button>
        ))}
      </div>
    </main>
  );
}

export default App;
