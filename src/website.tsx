import React, { useState, useEffect, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { motion } from "framer-motion";
import { Orb, AgentState } from "./components/Orb";
import { useTexture } from "@react-three/drei";
import { 
  Cpu, 
  Mic, 
  Zap, 
  ArrowRight,
  Monitor,
  Layout,
  MousePointer2
} from "lucide-react";
import "./Website.css";

// Preload the texture used in Orb.tsx to prevent Suspense flickering and context loss
useTexture.preload("https://storage.googleapis.com/eleven-public-cdn/images/perlin-noise.png");

const Github = ({ className }: { className?: string }) => (
  <svg 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
  >
    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
  </svg>
);

const GITHUB_URL = "https://github.com/SehajveerSingh2005/jen";
const RELEASES_URL = `${GITHUB_URL}/releases/latest`;

function Website() {
  const [orbScenario, setOrbScenario] = useState<{ colors: [string, string], state: AgentState }>({
    colors: ["#f8fafc", "#94a3b8"],
    state: "thinking"
  });

  useEffect(() => {
    const scenarios: { colors: [string, string], state: AgentState }[] = [
      { colors: ["#f8fafc", "#94a3b8"], state: "thinking" },
      { colors: ["#bae6fd", "#38bdf8"], state: "listening" },
      { colors: ["#f3e8ff", "#a855f7"], state: "thinking" },
      { colors: ["#ecfdf5", "#10b981"], state: "talking" },
    ];
    let i = 0;
    const interval = setInterval(() => {
      i = (i + 1) % scenarios.length;
      setOrbScenario(scenarios[i]);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen relative overflow-x-hidden bg-[#fcfcfc]">
      <div className="grain-overlay" />
      
      {/* Navigation */}
      <nav className="glass-nav">
        <div className="flex items-center gap-2">
          <div className="relative w-6 h-6">
            <div className="absolute inset-0 bg-black rounded-full" />
            <div className="absolute inset-[25%] bg-white rounded-full animate-pulse" />
          </div>
          <span className="font-medium tracking-tight text-black">jen</span>
        </div>
        <div className="flex items-center gap-6 text-sm font-medium text-black/60">
          <a href="#features" className="hover:text-black transition-colors">Features</a>
          <a href={GITHUB_URL} className="flex items-center gap-1.5 hover:text-black transition-colors">
            <Github className="w-4 h-4" />
            GitHub
          </a>
          <a href="#download" className="btn-primary py-2 px-5 text-xs shadow-none">Download</a>
        </div>
      </nav>

      <main>
        {/* Hero Section */}
        <section className="pt-48 pb-24 px-8 max-w-7xl mx-auto flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1 className="hero-text">
              Meet Jen.<br />
              <span className="text-[var(--text-muted)]">Your PC Companion.</span>
            </h1>
          </motion.div>

          <motion.p 
            className="sub-text"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            A minimal, ambient AI assistant that lives on your desktop. 
            Unobtrusive by design, powerful by nature.
          </motion.p>

          <div className="orb-viewport-stable" style={{ width: '380px', height: '380px' }}>
            <motion.div 
              className="w-full h-full relative z-10 flex items-center justify-center"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ 
                duration: 0.5, 
                ease: [0.34, 1.56, 0.64, 1] // Snappy overshoot pop
              }}
            >
              <div className="orb-glow opacity-50" />
              <Suspense fallback={<div className="w-full h-full rounded-full bg-black/5 animate-pulse" />}>
                <Orb 
                  className="w-full h-full" 
                  colors={orbScenario.colors} 
                  agentState={orbScenario.state}
                />
              </Suspense>
            </motion.div>
          </div>

          <motion.div
            className="flex flex-col md:flex-row gap-4 mt-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <a href="#download" className="btn-primary flex items-center gap-2 text-white">
              Get Started
              <ArrowRight className="w-4 h-4" />
            </a>
            <a href={GITHUB_URL} className="btn-secondary flex items-center gap-2">
              View Source
              <Github className="w-4 h-4" />
            </a>
          </motion.div>
        </section>

        {/* "PC Companion" Context Section */}
        <section className="py-32 px-8 bg-[#F2F2F7]/50">
          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-24 items-center">
              <div className="space-y-8">
                <h2 className="text-4xl md:text-5xl font-medium tracking-tight text-black">Always there,<br />never in the way.</h2>
                <p className="text-lg text-[var(--text-muted)] font-light leading-relaxed">
                  Jen isn't just another app window. It's an ambient presence on your screen that responds to your voice and helps you navigate your digital life without breaking your flow.
                </p>
                <ul className="space-y-6">
                  {[
                    { icon: MousePointer2, text: "Click-through transparency" },
                    { icon: Layout, text: "Lives right in the center of your flow" },
                    { icon: Monitor, text: "Cross-platform consistency" }
                  ].map((item, i) => (
                    <li key={i} className="flex items-center gap-4 text-sm font-medium text-black">
                      <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow-sm border border-black/5">
                        <item.icon className="w-4 h-4 opacity-40" />
                      </div>
                      {item.text}
                    </li>
                  ))}
                </ul>
              </div>
              
              <div className="mockup-container">
                <div className="mockup-wallpaper" />
                <div className="absolute inset-0 flex flex-col justify-end items-center pb-12">
                  {/* JEN CENTERED AT BOTTOM */}
                  <div className="w-20 h-20 relative">
                    <div className="absolute inset-0 bg-sky-400/20 blur-3xl rounded-full animate-pulse" />
                    <Suspense fallback={null}>
                      <Orb colors={["#bae6fd", "#38bdf8"]} agentState="listening" className="w-full h-full" />
                    </Suspense>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Grid */}
        <section id="features" className="py-32 px-8 max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 text-center md:text-left">
            <div className="feature-item">
              <div className="w-12 h-12 mb-8 rounded-2xl bg-[#f5f5f7] flex items-center justify-center border border-black/5 mx-auto md:mx-0">
                <Mic className="w-5 h-5 opacity-60 text-black" />
              </div>
              <h3 className="feature-title text-xl mb-4 text-black">Voice First</h3>
              <p className="feature-desc font-light text-[var(--text-muted)]">Natural language processing that understands your intent, not just your words.</p>
            </div>
            <div className="feature-item">
              <div className="w-12 h-12 mb-8 rounded-2xl bg-[#f5f5f7] flex items-center justify-center border border-black/5 mx-auto md:mx-0">
                <Cpu className="w-5 h-5 opacity-60 text-black" />
              </div>
              <h3 className="feature-title text-xl mb-4 text-black">Local Intelligence</h3>
              <p className="feature-desc font-light text-[var(--text-muted)]">Fast, secure, and private. Much of Jen's processing happens right on your machine.</p>
            </div>
            <div className="feature-item">
              <div className="w-12 h-12 mb-8 rounded-2xl bg-[#f5f5f7] flex items-center justify-center border border-black/5 mx-auto md:mx-0">
                <Zap className="w-5 h-5 opacity-60 text-black" />
              </div>
              <h3 className="feature-title text-xl mb-4 text-black">Instant Response</h3>
              <p className="feature-desc font-light text-[var(--text-muted)]">Zero friction. Activate with a hotkey or voice and get what you need instantly.</p>
            </div>
          </div>
        </section>

        {/* Download Section */}
        <section id="download" className="py-48 px-8 bg-black text-white rounded-[4rem] mx-4 my-4 overflow-hidden relative">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[20vw] font-bold text-white/[0.03] select-none pointer-events-none tracking-tighter uppercase whitespace-nowrap">
            Download
          </div>

          <div className="max-w-4xl mx-auto relative z-10 text-center">
            <h2 className="text-5xl md:text-7xl font-medium tracking-tight mb-16">Ready to meet Jen?</h2>
            
            <div className="flex flex-col md:flex-row gap-6 text-left">
              <a href={RELEASES_URL} className="flex-1 p-10 bg-white text-black rounded-[2.5rem] flex flex-col items-start transition-all hover:scale-[1.02] active:scale-[0.98]">
                <div className="flex items-center justify-between w-full mb-10">
                  <Monitor className="w-8 h-8 opacity-80" />
                  <ArrowRight className="w-5 h-5 -rotate-45" />
                </div>
                <span className="text-2xl font-bold">Windows x64</span>
                <span className="text-sm opacity-40 font-medium">Stable v0.1.0 (.msi)</span>
              </a>

              <div className="flex-1 p-10 bg-white/5 border border-white/10 rounded-[2.5rem] flex flex-col items-start opacity-30">
                <div className="flex items-center justify-between w-full mb-10">
                  <Monitor className="w-8 h-8 opacity-40" />
                </div>
                <span className="text-2xl font-bold">macOS Silicon</span>
                <span className="text-[10px] uppercase tracking-[0.2em] font-bold mt-2">Coming Soon</span>
              </div>
            </div>

            <a href={GITHUB_URL} className="mt-20 flex items-center gap-2 justify-center text-sm font-medium text-white/30 hover:text-white transition-colors">
              <Github className="w-4 h-4" />
              Open source on GitHub
            </a>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="py-20 px-8 border-t border-[#e8e8ed] text-center">
        <div className="flex items-center justify-center gap-2 mb-4 opacity-50 lowercase tracking-tight font-bold text-black">
          <div className="w-4 h-4 bg-black rounded-full" />
          jen
        </div>
        <p className="text-xs text-[var(--text-muted)] font-medium">
          Made with love by Sehaz. © {new Date().getFullYear()} Jen AI.
        </p>
      </footer>
    </div>
  );
}

const rootElement = document.getElementById("root");
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <Website />
    </React.StrictMode>
  );
}
