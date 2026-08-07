import { useState, useEffect, useMemo } from "react";
import { Orb, AgentState } from "./components/Orb";
import { listen } from "@tauri-apps/api/event";
import { motion, AnimatePresence } from "framer-motion";

type AppOrbState = "idle" | "startup" | "listening" | "processing" | "success" | "error" | "recording" | "speaking";

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

  useEffect(() => {
    if (state !== "idle") {
      const t1 = setTimeout(() => window.dispatchEvent(new Event("resize")), 50);
      const t2 = setTimeout(() => window.dispatchEvent(new Event("resize")), 360);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }
  }, [state]);

  const orbProps = useMemo(() => {
    // Premium Metallic Silver-Blue palette (Lighter)
    const defaultColors: [string, string] = ["#f8fafc", "#94a3b8"]; 
    
    switch (state) {
      case "startup":
        return { 
          agentState: "thinking" as AgentState, 
          colors: defaultColors 
        };
      case "listening":
      case "recording":
        return { 
          agentState: "listening" as AgentState, 
          colors: ["#bae6fd", "#38bdf8"] as [string, string] // Bright Sky Blue
        };
      case "processing":
        return { 
          agentState: "thinking" as AgentState, 
          colors: ["#f3e8ff", "#a855f7"] as [string, string] // Metallic Lavender
        };
      case "success":
        return { 
          agentState: "talking" as AgentState, 
          colors: ["#ecfdf5", "#10b981"] as [string, string] // Metallic Mint
        };
      case "speaking":
        return { 
          agentState: "talking" as AgentState, 
          colors: ["#fefce8", "#eab308"] as [string, string] // Warm Gold
        };
      case "error":
        return { 
          agentState: "thinking" as AgentState, 
          colors: ["#fef2f2", "#ef4444"] as [string, string] // Metallic Rose
        };
      default:
        return { 
          agentState: "listening" as AgentState, 
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
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ 
              duration: 0.3,
              ease: "easeOut",
            }}
            className="w-48 h-48 overflow-visible flex items-center justify-center"
          >
            <div className="w-full h-full flex items-center justify-center">
              <Orb {...orbProps} className="w-48 h-48" />
            </div>
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
