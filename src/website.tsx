import React, { useState, useEffect, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { Orb, AgentState } from "./components/Orb";
import { useTexture } from "@react-three/drei";
import { 
  Play, 
  SkipBack, 
  SkipForward, 
  Mail, 
  Moon,
  Monitor,
  ArrowRight
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

// Define the scroll sections, their associated chat bubble, and orb state
const SECTIONS = [
  { 
    id: 'hero', 
    bubble: null, 
    state: 'thinking' as AgentState, 
    colors: ["#f8fafc", "#94a3b8"] as [string, string] 
  },
  { 
    id: 'music', 
    bubble: "play God's Plan by Drake", 
    state: 'listening' as AgentState, 
    colors: ["#bae6fd", "#38bdf8"] as [string, string]
  },
  { 
    id: 'emails', 
    bubble: "summarize my recent emails", 
    state: 'thinking' as AgentState, 
    colors: ["#f3e8ff", "#a855f7"] as [string, string]
  },
  { 
    id: 'focus', 
    bubble: "turn on focus mode", 
    state: 'talking' as AgentState, 
    colors: ["#ecfdf5", "#10b981"] as [string, string]
  },
  {
    id: 'download',
    bubble: null,
    state: 'thinking' as AgentState,
    colors: ["#f8fafc", "#94a3b8"] as [string, string]
  }
];

function Website() {
  const [activeIdx, setActiveIdx] = useState(0);
  const [windowHeight, setWindowHeight] = useState(1000);
  
  useEffect(() => {
    setWindowHeight(window.innerHeight);
    const handleResize = () => setWindowHeight(window.innerHeight);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const { scrollY } = useScroll();
  
  const scrollDistance = windowHeight * 0.5;
  
  // When width/height is 380, center is at 380/2 = 190.
  // Container bottom is at 32px. Center from bottom = 190 + 32 = 222px.
  // We want the orb center to be 45vh from the bottom in the Hero section.
  const targetCenter = 0.45 * windowHeight;
  const startY = -(targetCenter - 222);

  // Animate width and height directly for perfect DOM layout
  const orbSize = useTransform(scrollY, [0, scrollDistance], [380, 180]);
  const orbY = useTransform(scrollY, [0, scrollDistance], [startY, 0]);

  return (
    <div className="min-h-screen relative overflow-x-hidden bg-[var(--bg-color)] font-sans selection:bg-black selection:text-white">
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
          <a href="#download" className="hover:text-black transition-colors">Download</a>
          <a href={GITHUB_URL} className="flex items-center gap-1.5 hover:text-black transition-colors">
            <Github className="w-4 h-4" />
            GitHub
          </a>
          <a href={RELEASES_URL} className="btn-primary py-2 px-5 text-xs shadow-none">Get Started</a>
        </div>
      </nav>

      {/* Fixed Anchor (Orb & Chat Bubble) */}
      <div className="fixed bottom-[32px] left-1/2 -translate-x-1/2 z-50 flex flex-col items-center pointer-events-none">
        
        {/* Animated Chat Bubble */}
        <div className="h-[60px] flex items-end justify-center mb-6">
          <AnimatePresence mode="wait">
            {SECTIONS[activeIdx].bubble && (
              <motion.div 
                key={SECTIONS[activeIdx].bubble}
                initial={{ opacity: 0, y: 15, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -15, scale: 0.9 }}
                transition={{ duration: 0.4, type: "spring", bounce: 0.4 }}
                className="px-6 py-3 bg-white/70 backdrop-blur-2xl border border-white/50 shadow-[0_8px_32px_rgba(0,0,0,0.08)] rounded-full text-[15px] font-medium text-black pointer-events-auto whitespace-nowrap"
              >
                "{SECTIONS[activeIdx].bubble}"
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Dynamic Scroll-Linked Orb */}
        <motion.div 
          className="relative pointer-events-auto drop-shadow-2xl cursor-pointer"
          style={{
            width: orbSize,
            height: orbSize,
            y: orbY
          }}
        >
          <div className="absolute inset-0 bg-sky-400/20 blur-[30px] rounded-full" />
          <Suspense fallback={<div className="w-full h-full rounded-full bg-black/5 animate-pulse" />}>
            <Orb 
              className="w-full h-full" 
              colors={SECTIONS[activeIdx].colors} 
              agentState={SECTIONS[activeIdx].state}
              resizeDebounce={0}
            />
          </Suspense>
        </motion.div>
      </div>

      <main className="relative w-full pb-[20vh]">
        
        {/* 1. Hero Section */}
        <motion.section 
          className="min-h-screen flex flex-col items-center justify-start pt-[12vh] relative z-10"
          onViewportEnter={() => setActiveIdx(0)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="text-center"
          >
            <h1 className="text-[5.5rem] md:text-[7.5rem] font-medium tracking-tight leading-[0.9] text-black mb-4">
              Meet Jen.
            </h1>
            <p className="text-xl md:text-3xl text-[var(--text-muted)] font-light tracking-tight max-w-sm md:max-w-none mx-auto">
              Intelligence that feels <span className="text-black italic pr-1">alive</span>.
            </p>
          </motion.div>
          
          <motion.div 
            className="absolute bottom-12 opacity-30 flex flex-col items-center gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            transition={{ delay: 1, duration: 1 }}
          >
            <span className="text-[10px] uppercase tracking-[0.2em] font-bold">Scroll</span>
            <div className="w-[1px] h-12 bg-black bg-gradient-to-b from-black to-transparent" />
          </motion.div>
        </motion.section>

        {/* 2. Showcase: Music */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(1)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="showcase-widget w-[320px]"
            initial={{ opacity: 0, scale: 0.9, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            <div className="w-full aspect-square rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-6 shadow-inner relative overflow-hidden">
              {/* Minimalist Vinyl/CD visual */}
              <div className="absolute -right-8 -bottom-8 w-48 h-48 border-[16px] border-black/10 rounded-full" />
              <div className="absolute right-4 bottom-4 w-12 h-12 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center">
                 <div className="w-3 h-3 bg-indigo-600 rounded-full" />
              </div>
            </div>
            <h3 className="text-xl font-bold mb-1 text-black">God's Plan</h3>
            <p className="text-sm text-[var(--text-muted)] font-medium mb-6">Drake</p>
            
            <div className="w-full h-1.5 bg-black/5 rounded-full mb-6 overflow-hidden">
              <motion.div 
                className="w-1/3 h-full bg-black rounded-full" 
                initial={{ width: "0%" }}
                whileInView={{ width: "33%" }}
                transition={{ duration: 1.5, ease: "easeOut" }}
              />
            </div>

            <div className="flex items-center justify-center gap-8">
              <SkipBack className="w-5 h-5 opacity-40 hover:opacity-100 transition-opacity cursor-pointer text-black" />
              <div className="w-14 h-14 bg-[#1d1d1f] rounded-full flex items-center justify-center cursor-pointer hover:scale-105 transition-transform shadow-[0_8px_16px_rgba(0,0,0,0.2)]">
                <Play className="w-5 h-5 text-white ml-1 fill-white" />
              </div>
              <SkipForward className="w-5 h-5 opacity-40 hover:opacity-100 transition-opacity cursor-pointer text-black" />
            </div>
          </motion.div>
        </motion.section>

        {/* 3. Showcase: Intelligence */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(2)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="showcase-widget w-[400px]"
            initial={{ opacity: 0, scale: 0.9, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            <div className="flex items-center gap-4 mb-8">
              <div className="w-12 h-12 bg-blue-500/10 rounded-[1.25rem] flex items-center justify-center">
                <Mail className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <h3 className="font-semibold text-lg text-black">Inbox Summary</h3>
                <p className="text-sm text-[var(--text-muted)]">3 unread emails</p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="p-5 bg-white/50 rounded-2xl border border-white shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-semibold text-blue-600">Action Required</p>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-black/30">Just Now</span>
                </div>
                <p className="text-[15px] text-black/80 leading-relaxed">Sarah requested your review on the Q3 marketing designs by 5 PM today.</p>
              </div>
              <div className="p-5 bg-black/[0.02] rounded-2xl border border-black/5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-semibold text-black">Newsletter</p>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-black/30">2h ago</span>
                </div>
                <p className="text-[15px] text-[var(--text-muted)] leading-relaxed">Framer released a new update regarding scroll-driven animations.</p>
              </div>
            </div>
          </motion.div>
        </motion.section>

        {/* 4. Showcase: System Control */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(3)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="showcase-widget w-[320px] text-center"
            initial={{ opacity: 0, scale: 0.9, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            <div className="w-20 h-20 bg-indigo-500 rounded-full flex items-center justify-center mx-auto mb-8 shadow-[0_12px_24px_rgba(99,102,241,0.3)]">
              <Moon className="w-8 h-8 text-white fill-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-black">Focus Mode On</h3>
            <p className="text-[15px] text-[var(--text-muted)] mb-10 leading-relaxed px-4">Notifications silenced until tomorrow morning.</p>
            
            <div className="w-16 h-9 bg-indigo-500 rounded-full p-1 mx-auto cursor-pointer shadow-inner">
              <motion.div 
                className="w-7 h-7 bg-white rounded-full shadow-sm"
                initial={{ x: 0 }}
                whileInView={{ x: 28 }}
                viewport={{ margin: "-20% 0px -20% 0px" }}
                transition={{ type: "spring", stiffness: 400, damping: 25, delay: 0.2 }}
              />
            </div>
          </motion.div>
        </motion.section>

        {/* 5. Minimalist Download footer */}
        <motion.section 
          id="download"
          className="min-h-screen flex flex-col items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(4)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <div className="max-w-3xl mx-auto text-center px-4">
            <h2 className="text-5xl md:text-7xl font-medium tracking-tight mb-8 text-black">Ready to try Jen?</h2>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center mt-12">
              <a href={RELEASES_URL} className="btn-primary flex items-center justify-center gap-3 py-5 px-10 text-lg">
                <Monitor className="w-5 h-5" />
                Download for Windows
              </a>
              <a href={GITHUB_URL} className="btn-secondary flex items-center justify-center gap-3 py-5 px-10 text-lg">
                <Github className="w-5 h-5" />
                View Source
              </a>
            </div>
            <p className="text-xs uppercase tracking-widest font-bold text-black/30 mt-12">macOS Coming Soon</p>
          </div>
        </motion.section>

      </main>
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
