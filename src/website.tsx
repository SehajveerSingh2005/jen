import React, { useState, useEffect, Suspense, useRef } from "react";
import ReactDOM from "react-dom/client";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { Orb, AgentState } from "./components/Orb";
import { useTexture } from "@react-three/drei";
import { 
  Play, 
  Pause,
  SkipBack, 
  SkipForward, 
  Search,
  Globe,
  Monitor,
  FileText,
  MessageSquare,
  Volume2,
  Mic2,
  ListMusic,
  Radio,
  Compass
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
    bubble: "play some Drake", 
    state: 'listening' as AgentState, 
    colors: ["#bae6fd", "#38bdf8"] as [string, string]
  },
  { 
    id: 'search', 
    bubble: "search google for latest space news", 
    state: 'thinking' as AgentState, 
    colors: ["#f3e8ff", "#a855f7"] as [string, string]
  },
  { 
    id: 'apps', 
    bubble: "open notepad", 
    state: 'talking' as AgentState, 
    colors: ["#ecfdf5", "#10b981"] as [string, string]
  },
  {
    id: 'conclusion',
    bubble: null,
    state: 'thinking' as AgentState,
    colors: ["#f8fafc", "#94a3b8"] as [string, string]
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
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (activeIdx === 1) {
      if (audioRef.current) {
        audioRef.current.play().then(() => setIsPlaying(true)).catch(e => {
          console.log("Auto-play prevented by browser policy", e);
          setIsPlaying(false);
        });
      }
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
        setIsPlaying(false);
      }
    }
  }, [activeIdx]);

  // Global click listener to gracefully handle browser autoplay blocks
  useEffect(() => {
    const handleGlobalClick = () => {
      if (activeIdx === 1 && !isPlaying && audioRef.current) {
        audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    };
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, [activeIdx, isPlaying]);
  
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
        <div className="flex items-center gap-3">
          <img src={`${import.meta.env.BASE_URL}logo.png`} alt="Jen Logo" className="w-8 h-8 drop-shadow-md" />
          <span className="font-medium tracking-tight text-black text-xl">Jen</span>
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

        {/* 2. Showcase: Music (Apple Music macOS UI) */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(1)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <audio 
            ref={audioRef} 
            src={`${import.meta.env.BASE_URL}gods-plan.mp3`} 
            loop 
            preload="auto"
            onLoadedMetadata={(e) => { e.currentTarget.currentTime = 87; }}
          />
          
          <motion.div 
            className="w-[800px] h-[500px] rounded-2xl bg-[#F5F5F7]/80 backdrop-blur-3xl shadow-[0_20px_40px_rgba(0,0,0,0.15)] border border-white/60 flex overflow-hidden relative"
            initial={{ opacity: 0, scale: 0.95, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            {/* Sidebar */}
            <div className="w-[240px] bg-black/[0.03] border-r border-black/5 flex flex-col relative z-20">
              {/* macOS Traffic Lights */}
              <div className="h-[52px] flex items-center px-4 gap-2">
                <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]" />
                <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]" />
              </div>

              {/* Sidebar Content */}
              <div className="px-3 py-2 space-y-1">
                <p className="text-xs font-semibold text-[var(--text-muted)] mb-2 px-2 mt-2">Apple Music</p>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md bg-black/5 text-[#FA243C]">
                  <Play className="w-4 h-4 fill-current" />
                  <span className="text-[13px] font-medium">Listen Now</span>
                </div>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-black/5 text-[var(--text-muted)] transition-colors cursor-pointer">
                  <Compass className="w-4 h-4" />
                  <span className="text-[13px] font-medium">Browse</span>
                </div>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-black/5 text-[var(--text-muted)] transition-colors cursor-pointer">
                  <Radio className="w-4 h-4" />
                  <span className="text-[13px] font-medium">Radio</span>
                </div>
              </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col relative z-10 bg-white/20">
              {/* Top Control Bar */}
              <div className="h-[52px] flex items-center justify-between px-6 border-b border-black/5 bg-white/40 backdrop-blur-md absolute top-0 left-0 right-0 z-20">
                {/* Transport Controls */}
                <div className="flex items-center gap-6">
                  <SkipBack className="w-4 h-4 text-[var(--text-muted)] hover:text-black cursor-pointer transition-colors" />
                  <button 
                    onClick={() => {
                      if (isPlaying) { 
                        audioRef.current?.pause(); 
                        setIsPlaying(false); 
                      } else { 
                        audioRef.current?.play().then(() => setIsPlaying(true)); 
                      }
                    }}
                    className="w-8 h-8 rounded-full bg-black/[0.05] flex items-center justify-center hover:bg-black/10 transition-colors"
                  >
                    {isPlaying ? <Pause className="w-4 h-4 text-black fill-black" /> : <Play className="w-4 h-4 text-black fill-black ml-0.5" />}
                  </button>
                  <SkipForward className="w-4 h-4 text-[var(--text-muted)] hover:text-black cursor-pointer transition-colors" />
                </div>

                {/* Scrubber / LCD display */}
                <div className="w-[240px] h-8 rounded-md bg-black/[0.03] border border-black/5 flex items-center justify-center relative overflow-hidden">
                   {isPlaying && (
                     <motion.div 
                       className="absolute left-0 top-0 bottom-0 bg-black/5"
                       initial={{ width: "0%" }}
                       animate={{ width: "100%" }}
                       transition={{ duration: 240, ease: "linear" }}
                     />
                   )}
                   <span className="text-[11px] font-medium text-black z-10 relative">Drake — God's Plan</span>
                </div>

                {/* Volume & Extras */}
                <div className="flex items-center gap-4">
                  <Mic2 className="w-4 h-4 text-[var(--text-muted)]" />
                  <ListMusic className="w-4 h-4 text-[var(--text-muted)]" />
                  <div className="flex items-center gap-2">
                    <Volume2 className="w-4 h-4 text-[var(--text-muted)]" />
                    <div className="w-16 h-1.5 rounded-full bg-black/10">
                      <div className="w-2/3 h-full rounded-full bg-[var(--text-muted)]" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Now Playing Visuals */}
              <div className="flex-1 pt-[52px] flex items-center justify-center p-12">
                 <div className="flex gap-12 items-center w-full max-w-2xl pl-8">
                    {/* Album Art */}
                    <div className="w-[240px] h-[240px] rounded-lg shadow-[0_20px_40px_rgba(0,0,0,0.2)] relative overflow-hidden shrink-0 group">
                      <img src={`${import.meta.env.BASE_URL}gods-plan.jpg`} alt="God's Plan" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>

                    {/* Song Info */}
                    <div className="flex flex-col">
                      <h2 className="text-3xl font-bold text-black tracking-tight mb-2">God's Plan</h2>
                      <p className="text-lg text-[#FA243C] font-medium mb-4">Drake</p>
                      <p className="text-[13px] text-[var(--text-muted)] font-medium">Scorpion • 2018</p>
                    </div>
                 </div>
              </div>
            </div>
          </motion.div>
        </motion.section>

        {/* 3. Showcase: Smart Search */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(2)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="w-[680px] rounded-2xl bg-[#F5F5F7]/90 backdrop-blur-3xl shadow-[0_30px_60px_rgba(0,0,0,0.15)] border border-white/60 overflow-hidden flex flex-col"
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {/* Search Input Area */}
            <div className="flex items-center gap-4 px-6 py-5 border-b border-black/5 bg-white/30">
              <Search className="w-8 h-8 text-[var(--text-muted)]" />
              <div className="flex-1 text-3xl font-light text-black outline-none bg-transparent">
                 latest space news
              </div>
              <img src={`${import.meta.env.BASE_URL}logo.png`} alt="Jen" className="w-8 h-8 opacity-20 grayscale" />
            </div>

            {/* Results Area */}
            <div className="flex h-[380px]">
               {/* Left Sidebar (Categories) */}
               <div className="w-[180px] border-r border-black/5 p-2 flex flex-col gap-1 bg-white/20">
                  <div className="px-3 py-1.5 rounded-lg bg-[#0062E3] text-white font-medium text-[13px] flex items-center justify-between shadow-sm">
                     Top Hits
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 font-medium text-[13px]">
                     Siri Knowledge
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 font-medium text-[13px]">
                     News
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 font-medium text-[13px]">
                     Web Search
                  </div>
               </div>

               {/* Right Content (Rich Result) */}
               <div className="flex-1 p-6 bg-white/10 flex flex-col">
                  <div className="flex gap-6 items-start">
                     {/* Thumbnail */}
                     <div className="w-[120px] h-[120px] rounded-xl bg-[url('https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?q=80&w=2574&auto=format&fit=crop')] bg-cover bg-center shadow-md flex-shrink-0" />
                     {/* Info */}
                     <div className="flex flex-col">
                        <h3 className="text-2xl font-bold text-black mb-1">James Webb Space Telescope</h3>
                        <p className="text-sm font-medium text-[var(--text-muted)] mb-3">Siri Knowledge</p>
                        <p className="text-[13px] text-black/70 leading-relaxed">
                          The James Webb Space Telescope is a space telescope designed primarily to conduct infrared astronomy. As the largest telescope in space, it is equipped with high-resolution and highly sensitive instruments, allowing it to view objects too old, distant, or faint for the Hubble Space Telescope.
                        </p>
                        <div className="mt-4 flex gap-2">
                           <div className="px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 text-[11px] font-bold uppercase tracking-wide">NASA.gov</div>
                           <div className="px-3 py-1 rounded-full bg-black/5 text-black/60 text-[11px] font-bold uppercase tracking-wide">Wikipedia</div>
                        </div>
                     </div>
                  </div>
               </div>
            </div>
          </motion.div>
        </motion.section>

        {/* 4. Showcase: App Control */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(3)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="w-[900px] h-[560px] rounded-2xl bg-cover bg-center bg-[url('https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2564&auto=format&fit=crop')] shadow-[0_20px_40px_rgba(0,0,0,0.2)] border border-white/20 relative overflow-hidden flex flex-col"
            initial={{ opacity: 0, scale: 0.95, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
             {/* Desktop Area with Windows */}
             <div className="flex-1 relative">
                {/* Notepad Window */}
                <motion.div 
                  className="absolute left-[80px] top-[60px] w-[380px] h-[320px] rounded-xl bg-[#F3F3F3]/90 backdrop-blur-2xl border border-white shadow-[0_12px_24px_rgba(0,0,0,0.2)] flex flex-col overflow-hidden"
                  initial={{ opacity: 0, y: 30, scale: 0.9 }}
                  whileInView={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", bounce: 0.3 }}
                >
                  <div className="h-10 flex items-center px-4 justify-between border-b border-black/5 bg-white/50">
                    <div className="flex items-center gap-2">
                       <FileText className="w-4 h-4 text-sky-500" />
                       <span className="text-[11px] font-medium text-black">Untitled - Notepad</span>
                    </div>
                    <div className="flex gap-4 items-center">
                      <div className="w-3 h-0.5 bg-black/40" />
                      <div className="w-3 h-3 border border-black/40 rounded-[2px]" />
                      <div className="w-3 h-3 flex items-center justify-center relative">
                        <div className="w-0.5 h-3 bg-black/40 rotate-45 absolute" />
                        <div className="w-0.5 h-3 bg-black/40 -rotate-45 absolute" />
                      </div>
                    </div>
                  </div>
                  <div className="flex-1 p-5 bg-white/50">
                    <p className="text-[14px] font-mono text-black/80 mb-1">Meeting Notes:</p>
                    <p className="text-[14px] font-mono text-black/80">- Discuss Q3 roadmap</p>
                    <p className="text-[14px] font-mono text-black/80">- Finalize UI designs</p>
                    <motion.div 
                      className="w-1.5 h-3.5 bg-black/80 inline-block ml-1 align-middle"
                      animate={{ opacity: [1, 0] }}
                      transition={{ repeat: Infinity, duration: 0.8 }}
                    />
                  </div>
                </motion.div>

                {/* Discord Window */}
                <motion.div 
                  className="absolute right-[80px] top-[100px] w-[420px] h-[340px] rounded-xl bg-[#313338]/95 backdrop-blur-2xl border border-white/10 shadow-[0_16px_32px_rgba(0,0,0,0.3)] flex flex-col overflow-hidden"
                  initial={{ opacity: 0, y: 30, scale: 0.9 }}
                  whileInView={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: 0.35, type: "spring", bounce: 0.3 }}
                >
                   <div className="h-8 flex items-center px-4 justify-between bg-[#1E1F22]">
                     <span className="text-[11px] font-bold text-[var(--text-muted)]">DISCORD</span>
                     <div className="flex gap-4 items-center">
                      <div className="w-3 h-0.5 bg-white/40" />
                      <div className="w-3 h-3 border border-white/40 rounded-[2px]" />
                      <div className="w-3 h-3 flex items-center justify-center relative">
                        <div className="w-0.5 h-3 bg-white/40 rotate-45 absolute" />
                        <div className="w-0.5 h-3 bg-white/40 -rotate-45 absolute" />
                      </div>
                    </div>
                   </div>
                   <div className="flex-1 flex">
                     <div className="w-16 bg-[#1E1F22] flex flex-col items-center py-3 gap-2">
                        <div className="w-10 h-10 rounded-[16px] bg-[#5865F2] flex items-center justify-center">
                          <MessageSquare className="w-6 h-6 text-white" />
                        </div>
                        <div className="w-8 h-0.5 bg-[#313338] rounded-full my-1" />
                        <div className="w-10 h-10 rounded-[20px] bg-[#313338] flex items-center justify-center text-white font-bold">D</div>
                     </div>
                     <div className="w-[120px] bg-[#2B2D31] flex flex-col p-3">
                        <div className="h-3 w-16 bg-[#313338] rounded-full mb-4" />
                        <div className="h-2 w-20 bg-white/20 rounded-full mb-3" />
                        <div className="h-2 w-14 bg-[#313338] rounded-full mb-3" />
                        <div className="h-2 w-16 bg-[#313338] rounded-full" />
                     </div>
                     <div className="flex-1 bg-[#313338] p-4 flex flex-col justify-end">
                        <div className="w-full h-10 rounded-lg bg-[#383A40] mb-2 border border-white/5" />
                     </div>
                   </div>
                </motion.div>
             </div>

             {/* Windows 11 Taskbar */}
             <div className="h-14 bg-[#F3F3F3]/80 backdrop-blur-3xl border-t border-white/40 flex items-center justify-center gap-1 z-20">
                <div className="w-10 h-10 rounded-md hover:bg-white/50 flex items-center justify-center transition-colors cursor-pointer">
                   <div className="w-5 h-5 grid grid-cols-2 gap-0.5">
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                   </div>
                </div>
                {/* Search */}
                <div className="w-32 h-8 bg-white/80 rounded-full border border-black/5 flex items-center px-3 gap-2 ml-1 mr-2 shadow-sm">
                   <Search className="w-3 h-3 text-black/50" />
                   <span className="text-[11px] font-medium text-black/50">Search</span>
                </div>
                {/* Apps */}
                <div className="w-10 h-10 rounded-md hover:bg-white/50 flex items-center justify-center transition-colors cursor-pointer relative">
                   <FileText className="w-6 h-6 text-sky-500" />
                   <div className="absolute bottom-0 w-1.5 h-1 rounded-full bg-black/40" />
                </div>
                <div className="w-10 h-10 rounded-md hover:bg-white/50 flex items-center justify-center transition-colors cursor-pointer relative">
                   <MessageSquare className="w-6 h-6 text-[#5865F2]" />
                   <div className="absolute bottom-0 w-4 h-1 rounded-full bg-[#00A4EF]" />
                </div>
             </div>
          </motion.div>
        </motion.section>

        {/* 5. Conclusion Section */}
        <motion.section 
          className="min-h-[70vh] flex flex-col items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(4)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="text-center px-4 max-w-2xl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-4xl md:text-5xl font-medium tracking-tight mb-6 text-black leading-tight">
              Unobtrusive.<br/><span className="text-[var(--text-muted)] italic">Always ready.</span>
            </h2>
            <p className="text-lg md:text-xl text-[var(--text-muted)] font-light leading-relaxed">
              Jen is designed to live quietly at the bottom of your screen, waiting for your wake word. No heavy windows, no distractions. Just raw utility.
            </p>
          </motion.div>
        </motion.section>

        {/* 6. Minimalist Download footer */}
        <motion.section 
          id="download"
          className="min-h-screen flex flex-col items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(5)}
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
