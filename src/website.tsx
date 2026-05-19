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
  Monitor,
  FileText,
  MessageSquare,
  Volume2,
  Mic2,
  Keyboard,
  ListMusic,
  Radio,
  Compass,
  Cpu,
  Zap,
  Eye,
  Calendar,
  Paintbrush,
  ArrowLeft,
  History,
  Sun,
  Moon
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
const RELEASES_URL = "https://github.com/SehajveerSingh2005/jen/releases/latest";

// Define the scroll sections, their associated chat bubble, and orb state
const SECTIONS = [
  { 
    id: 'hero', 
    bubble: null, 
    state: 'thinking' as AgentState, 
    colors: ["#f8fafc", "#94a3b8"] as [string, string] 
  },
  { 
    id: 'wake', 
    bubble: "Hey Jen", 
    state: 'listening' as AgentState, 
    colors: ["#bae6fd", "#38bdf8"] as [string, string]
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
    id: 'roadmap',
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
  const [downloadUrl, setDownloadUrl] = useState(RELEASES_URL);
  const [version, setVersion] = useState("v0.1.0");
  const [isAudioUnlocked, setIsAudioUnlocked] = useState(false);
  const [view, setView] = useState<'home' | 'changelog'>('home');
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      if (saved === 'light' || saved === 'dark') return saved;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  });

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [view]);

  useEffect(() => {
    if (view !== 'home' && audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }, [view]);

  useEffect(() => {
    fetch("https://api.github.com/repos/SehajveerSingh2005/jen/releases/latest")
      .then(res => res.json())
      .then(data => {
        if (data && data.tag_name) {
          setVersion(data.tag_name);
        }
        if (data && data.assets) {
          // Look for an MSI or EXE installer
          const installerAsset = data.assets.find((a: any) => a.name.endsWith('.msi') || a.name.endsWith('-setup.exe'));
          if (installerAsset) {
            setDownloadUrl(installerAsset.browser_download_url);
          }
        }
      })
      .catch(err => console.error("Failed to fetch latest release:", err));
  }, []);

  useEffect(() => {
    if (activeIdx === 2) {
      if (audioRef.current) {
        audioRef.current.play().then(() => {
          setIsPlaying(true);
          setIsAudioUnlocked(true);
        }).catch(e => {
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
  }, [activeIdx, isAudioUnlocked]);

  // Global click listener to unlock audio APIs on first interaction
  useEffect(() => {
    if (isAudioUnlocked) return;
    const handleGlobalInteraction = () => {
      setIsAudioUnlocked(true);
    };
    window.addEventListener('click', handleGlobalInteraction, { once: true });
    window.addEventListener('touchstart', handleGlobalInteraction, { once: true });
    return () => {
      window.removeEventListener('click', handleGlobalInteraction);
      window.removeEventListener('touchstart', handleGlobalInteraction);
    };
  }, [isAudioUnlocked]);
  
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
  const startY = -(targetCenter - 275);

  // Animate width and height directly for perfect DOM layout
  const orbSize = useTransform(scrollY, [0, scrollDistance], [380, 180]);
  const orbY = useTransform(scrollY, [0, scrollDistance], [startY, 0]);

  return (
    <div className="min-h-screen relative overflow-x-hidden bg-[var(--bg-color)] font-sans selection:bg-black selection:text-white dark:selection:bg-white dark:selection:text-black transition-colors duration-350">
      <div className="grain-overlay" />
      
      {/* Navigation */}
      <nav className="glass-nav">
        <div 
          onClick={() => setView('home')} 
          className="flex items-center gap-3 cursor-pointer group"
        >
          <img 
            src={`${import.meta.env.BASE_URL}logo.png`} 
            alt="Jen Logo" 
            className="w-8 h-8 drop-shadow-md group-hover:scale-105 transition-transform" 
          />
          <span className="font-medium tracking-tight text-black dark:text-white text-xl">Jen</span>
        </div>
        <div className="flex items-center gap-6 text-sm font-medium text-black/60 dark:text-white/60">
          <button 
            onClick={() => setView(view === 'home' ? 'changelog' : 'home')}
            className={`hover:text-black dark:hover:text-white transition-colors cursor-pointer text-sm border-none bg-transparent flex items-center h-8 ${
              view === 'changelog' 
                ? 'text-black dark:text-white font-semibold' 
                : 'text-black/60 dark:text-white/60'
            }`}
          >
            Changelog
          </button>
          <a 
            href={GITHUB_URL} 
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center h-8 hover:text-black dark:hover:text-white transition-colors"
          >
            GitHub
          </a>
          
          <div className="w-px h-4 bg-black/10 dark:bg-white/15" />

          {/* Theme Switcher */}
          <button
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="w-8 h-8 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer text-black/65 dark:text-white/65 hover:text-black dark:hover:text-white border-none bg-transparent flex items-center justify-center"
            aria-label="Toggle Theme"
          >
            {theme === 'light' ? (
              <Moon className="w-4 h-4" />
            ) : (
              <Sun className="w-4 h-4" />
            )}
          </button>

          <a href={downloadUrl} className="btn-primary h-9 px-5 text-[13px] shadow-sm flex items-center justify-center">
            Download
          </a>
        </div>
      </nav>

      {/* Fixed Anchor (Orb & Chat Bubble) */}
      {view === 'home' && (
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
                  className="px-6 py-3 bg-white/70 dark:bg-[#1A1A1E]/75 backdrop-blur-2xl border border-white/50 dark:border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.08)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.4)] rounded-full text-[15px] font-medium text-black dark:text-white pointer-events-auto whitespace-nowrap"
                >
                  "{SECTIONS[activeIdx].bubble}"
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Dynamic Scroll-Linked Orb */}
          <motion.div 
            className="relative pointer-events-auto cursor-pointer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ 
              duration: 0.5, 
              delay: 0.5,
              ease: "easeOut"
            }}
            style={{
              width: orbSize,
              height: orbSize,
              y: orbY,
              filter: "drop-shadow(0 20px 50px rgba(0,0,0,0.1))"
            }}
          >
            <div className="absolute inset-0 bg-sky-400/10 blur-[40px] rounded-full" />
            <Suspense fallback={<div className="w-full h-full rounded-full bg-black/[0.03] animate-pulse" />}>
              <Orb 
                className="w-full h-full" 
                colors={SECTIONS[activeIdx].colors} 
                agentState={SECTIONS[activeIdx].state}
                resizeDebounce={0}
              />
            </Suspense>
          </motion.div>
        </div>
      )}

      <main className="relative w-full pb-[20vh]">
        {view === 'home' ? (
          <>
            {/* 1. Hero Section */}
            <motion.section 
              className="min-h-screen flex flex-col items-center justify-start pt-[12vh] relative z-10"
          onViewportEnter={() => setActiveIdx(0)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div
            initial="hidden"
            animate="visible"
            className="text-center"
          >
            <motion.div 
              variants={{
                hidden: { opacity: 0, y: 15 },
                visible: { opacity: 1, y: 0 }
              }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 mb-8"
            >
               <div className="w-2 h-2 rounded-full bg-[#27C93F] animate-pulse" />
               <span className="text-[11px] font-bold tracking-widest uppercase text-black/60 dark:text-white/60">{version} — Public Beta</span>
            </motion.div>
            
            <motion.h1 
              variants={{
                hidden: { opacity: 0, y: 25 },
                visible: { opacity: 1, y: 0 }
              }}
              transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="text-[5.5rem] md:text-[7.5rem] font-medium tracking-tight leading-[0.9] text-black dark:text-white mb-4"
            >
              Meet Jen.
            </motion.h1>
            
            <motion.p 
              variants={{
                hidden: { opacity: 0, y: 20 },
                visible: { opacity: 1, y: 0 }
              }}
              transition={{ duration: 0.8, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="text-xl md:text-3xl text-[var(--text-muted)] font-light tracking-tight max-w-sm md:max-w-none mx-auto"
            >
              Voice control that feels <span className="text-black dark:text-white italic pr-1">native</span>.
            </motion.p>
          </motion.div>
          
          <motion.div 
            className="absolute bottom-12 opacity-30 flex flex-col items-center gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            transition={{ delay: 1, duration: 1 }}
          >
            <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-black dark:text-white">Scroll</span>
            <div className="w-[1px] h-12 bg-black dark:bg-white bg-gradient-to-b from-black dark:from-white to-transparent" />
          </motion.div>
        </motion.section>

        {/* 1.5. Wake Word & Keybind */}
        <motion.section 
          className="min-h-[60vh] flex flex-col items-center justify-center relative z-10 py-20"
          onViewportEnter={() => setActiveIdx(1)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="flex flex-col md:flex-row gap-12 max-w-4xl px-6"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ duration: 0.8 }}
          >
            <div className="flex-1 flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-black/5 dark:bg-white/5 flex items-center justify-center mb-6 shadow-sm border border-black/5 dark:border-white/5">
                <Mic2 className="w-8 h-8 text-black dark:text-white" />
              </div>
              <h3 className="text-2xl font-medium text-black dark:text-white mb-3">Voice Activated</h3>
              <p className="text-lg text-[var(--text-muted)] font-light leading-relaxed">
                Just say <span className="text-black dark:text-white font-medium italic">"Hey Jen"</span> to wake Jen up. Always listening, yet never intrusive.
              </p>
            </div>
            
            <div className="flex-1 flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-black/5 dark:bg-white/5 flex items-center justify-center mb-6 shadow-sm border border-black/5 dark:border-white/5">
                <Keyboard className="w-8 h-8 text-black dark:text-white" />
              </div>
              <h3 className="text-2xl font-medium text-black dark:text-white mb-3">Keyboard Ready</h3>
              <p className="text-lg text-[var(--text-muted)] font-light leading-relaxed">
                Prefer keys? Use <span className="text-black dark:text-white font-medium">Ctrl + Shift + R</span> to trigger Jen instantly from any application.
              </p>
            </div>
          </motion.div>
        </motion.section>

        {/* 2. Showcase: Music (Apple Music macOS UI) */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(2)}
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
            className="w-[800px] h-[500px] rounded-2xl bg-[#F5F5F7]/80 dark:bg-[#1A1A1E]/80 backdrop-blur-3xl shadow-[0_20px_40px_rgba(0,0,0,0.15)] dark:shadow-[0_20px_40px_rgba(0,0,0,0.5)] border border-white/60 dark:border-white/5 flex overflow-hidden relative"
            initial={{ opacity: 0, scale: 0.95, y: 40 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            {/* Sidebar */}
            <div className="w-[240px] bg-black/[0.03] dark:bg-white/[0.02] border-r border-black/5 dark:border-white/5 flex flex-col relative z-20">
              {/* macOS Traffic Lights */}
              <div className="h-[52px] flex items-center px-4 gap-2">
                <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]" />
                <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]" />
              </div>

              {/* Sidebar Content */}
              <div className="px-3 py-2 space-y-1">
                <p className="text-xs font-semibold text-[var(--text-muted)] mb-2 px-2 mt-2">Apple Music</p>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md bg-black/5 dark:bg-white/5 text-[#FA243C]">
                  <Play className="w-4 h-4 fill-current" />
                  <span className="text-[13px] font-medium">Listen Now</span>
                </div>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/5 text-[var(--text-muted)] transition-colors cursor-pointer">
                  <Compass className="w-4 h-4" />
                  <span className="text-[13px] font-medium">Browse</span>
                </div>
                <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/5 text-[var(--text-muted)] transition-colors cursor-pointer">
                  <Radio className="w-4 h-4" />
                  <span className="text-[13px] font-medium">Radio</span>
                </div>
              </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col relative z-10 bg-white/20 dark:bg-black/20">
              {/* Top Control Bar */}
              <div className="h-[52px] flex items-center justify-between px-6 border-b border-black/5 dark:border-white/5 bg-white/40 dark:bg-black/40 backdrop-blur-md absolute top-0 left-0 right-0 z-20">
                {/* Transport Controls */}
                <div className="flex items-center gap-6">
                  <SkipBack className="w-4 h-4 text-[var(--text-muted)] hover:text-black dark:hover:text-white cursor-pointer transition-colors" />
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isPlaying) { 
                        audioRef.current?.pause(); 
                        setIsPlaying(false); 
                      } else { 
                        audioRef.current?.play().then(() => {
                          setIsPlaying(true);
                          setIsAudioUnlocked(true);
                        }); 
                      }
                    }}
                    className="w-8 h-8 rounded-full bg-black/[0.05] dark:bg-white/[0.05] flex items-center justify-center hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                  >
                    {isPlaying ? <Pause className="w-4 h-4 text-black dark:text-white fill-black dark:fill-white" /> : <Play className="w-4 h-4 text-black dark:text-white fill-black dark:fill-white ml-0.5" />}
                  </button>
                  <SkipForward className="w-4 h-4 text-[var(--text-muted)] hover:text-black dark:hover:text-white cursor-pointer transition-colors" />
                </div>

                {/* Scrubber / LCD display */}
                <div className="w-[240px] h-8 rounded-md bg-black/[0.03] dark:bg-white/[0.03] border border-black/5 dark:border-white/5 flex items-center justify-center relative overflow-hidden">
                   {isPlaying && (
                     <motion.div 
                       className="absolute left-0 top-0 bottom-0 bg-black/5 dark:bg-white/5"
                       initial={{ width: "0%" }}
                       animate={{ width: "100%" }}
                       transition={{ duration: 240, ease: "linear" }}
                     />
                   )}
                   <span className="text-[11px] font-medium text-black dark:text-white z-10 relative">Drake — God's Plan</span>
                </div>

                {/* Volume & Extras */}
                <div className="flex items-center gap-4">
                  <Mic2 className="w-4 h-4 text-[var(--text-muted)]" />
                  <ListMusic className="w-4 h-4 text-[var(--text-muted)]" />
                  <div className="flex items-center gap-2">
                    <Volume2 className="w-4 h-4 text-[var(--text-muted)]" />
                    <div className="w-16 h-1.5 rounded-full bg-black/10 dark:bg-white/10">
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
                      <h2 className="text-3xl font-bold text-black dark:text-white tracking-tight mb-2">God's Plan</h2>
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
          onViewportEnter={() => setActiveIdx(3)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="w-[680px] rounded-2xl bg-[#F5F5F7]/90 dark:bg-[#1A1A1E]/90 backdrop-blur-3xl shadow-[0_30px_60px_rgba(0,0,0,0.15)] dark:shadow-[0_30px_60px_rgba(0,0,0,0.5)] border border-white/60 dark:border-white/5 overflow-hidden flex flex-col"
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {/* Search Input Area */}
            <div className="flex items-center gap-4 px-6 py-5 border-b border-black/5 dark:border-white/5 bg-white/30 dark:bg-black/30">
              <Search className="w-8 h-8 text-[var(--text-muted)]" />
              <div className="flex-1 text-3xl font-light text-black dark:text-white outline-none bg-transparent">
                 latest space news
              </div>
              <img src={`${import.meta.env.BASE_URL}logo.png`} alt="Jen" className="w-8 h-8 opacity-20 grayscale dark:invert" />
            </div>

            {/* Results Area */}
            <div className="flex h-[380px]">
               {/* Left Sidebar (Categories) */}
               <div className="w-[180px] border-r border-black/5 dark:border-white/5 p-2 flex flex-col gap-1 bg-white/20 dark:bg-black/20">
                  <div className="px-3 py-1.5 rounded-lg bg-[#0062E3] text-white font-medium text-[13px] flex items-center justify-between shadow-sm">
                     Top Hits
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 dark:text-white/70 font-medium text-[13px]">
                     Siri Knowledge
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 dark:text-white/70 font-medium text-[13px]">
                     News
                  </div>
                  <div className="px-3 py-1.5 rounded-lg text-black/70 dark:text-white/70 font-medium text-[13px]">
                     Web Search
                  </div>
               </div>

               {/* Right Content (Rich Result) */}
               <div className="flex-1 p-6 bg-white/10 dark:bg-black/10 flex flex-col">
                  <div className="flex gap-6 items-start">
                     {/* Thumbnail */}
                     <div className="w-[120px] h-[120px] rounded-xl bg-[url('https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?q=80&w=2574&auto=format&fit=crop')] bg-cover bg-center shadow-md flex-shrink-0" />
                     {/* Info */}
                     <div className="flex flex-col">
                        <h3 className="text-2xl font-bold text-black dark:text-white mb-1">James Webb Space Telescope</h3>
                        <p className="text-sm font-medium text-[var(--text-muted)] mb-3">Siri Knowledge</p>
                        <p className="text-[13px] text-black/70 dark:text-white/70 leading-relaxed">
                          The James Webb Space Telescope is a space telescope designed primarily to conduct infrared astronomy. As the largest telescope in space, it is equipped with high-resolution and highly sensitive instruments, allowing it to view objects too old, distant, or faint for the Hubble Space Telescope.
                        </p>
                        <div className="mt-4 flex gap-2">
                           <div className="px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 text-[11px] font-bold uppercase tracking-wide">NASA.gov</div>
                           <div className="px-3 py-1 rounded-full bg-black/5 dark:bg-white/5 text-black/60 dark:text-white/65 text-[11px] font-bold uppercase tracking-wide">Wikipedia</div>
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
          onViewportEnter={() => setActiveIdx(4)}
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
                  className="absolute left-[80px] top-[60px] w-[380px] h-[320px] rounded-xl bg-[#F3F3F3]/90 dark:bg-[#1C1C1E]/90 backdrop-blur-2xl border border-white dark:border-white/5 shadow-[0_12px_24px_rgba(0,0,0,0.2)] dark:shadow-[0_12px_24px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden"
                  initial={{ opacity: 0, y: 30, scale: 0.9 }}
                  whileInView={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", bounce: 0.3 }}
                >
                  <div className="h-10 flex items-center px-4 justify-between border-b border-black/5 dark:border-white/5 bg-white/50 dark:bg-black/50">
                    <div className="flex items-center gap-2">
                       <FileText className="w-4 h-4 text-sky-500" />
                       <span className="text-[11px] font-medium text-black dark:text-white">Untitled - Notepad</span>
                    </div>
                    <div className="flex gap-4 items-center">
                      <div className="w-3 h-0.5 bg-black/40 dark:bg-white/40" />
                      <div className="w-3 h-3 border border-black/40 dark:border-white/40 rounded-[2px]" />
                      <div className="w-3 h-3 flex items-center justify-center relative">
                        <div className="w-0.5 h-3 bg-black/40 dark:bg-white/40 rotate-45 absolute" />
                        <div className="w-0.5 h-3 bg-black/40 dark:bg-white/40 -rotate-45 absolute" />
                      </div>
                    </div>
                  </div>
                  <div className="flex-1 p-5 bg-white/50 dark:bg-black/50">
                    <p className="text-[14px] font-mono text-black/80 dark:text-white/80 mb-1">Meeting Notes:</p>
                    <p className="text-[14px] font-mono text-black/80 dark:text-white/80">- Discuss Q3 roadmap</p>
                    <p className="text-[14px] font-mono text-black/80 dark:text-white/80">- Finalize UI designs</p>
                    <motion.div 
                      className="w-1.5 h-3.5 bg-black/80 dark:bg-white/80 inline-block ml-1 align-middle"
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
             <div className="h-14 bg-[#F3F3F3]/80 dark:bg-[#1E1E1E]/80 backdrop-blur-3xl border-t border-white/40 dark:border-white/5 flex items-center justify-center gap-1 z-20">
                <div className="w-10 h-10 rounded-md hover:bg-white/50 dark:hover:bg-white/10 flex items-center justify-center transition-colors cursor-pointer">
                   <div className="w-5 h-5 grid grid-cols-2 gap-0.5">
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                     <div className="bg-[#00A4EF] rounded-[2px]" />
                   </div>
                </div>
                {/* Search */}
                <div className="w-32 h-8 bg-white/80 dark:bg-[#202020]/80 rounded-full border border-black/5 dark:border-white/5 flex items-center px-3 gap-2 ml-1 mr-2 shadow-sm">
                   <Search className="w-3 h-3 text-black/50" />
                   <span className="text-[11px] font-medium text-black/50">Search</span>
                </div>
                {/* Apps */}
                <div className="w-10 h-10 rounded-md hover:bg-white/50 dark:hover:bg-white/10 flex items-center justify-center transition-colors cursor-pointer relative">
                   <FileText className="w-6 h-6 text-sky-500" />
                   <div className="absolute bottom-0 w-1.5 h-1 rounded-full bg-black/40 dark:bg-white/40" />
                </div>
                <div className="w-10 h-10 rounded-md hover:bg-white/50 dark:hover:bg-white/10 flex items-center justify-center transition-colors cursor-pointer relative">
                   <MessageSquare className="w-6 h-6 text-[#5865F2]" />
                   <div className="absolute bottom-0 w-4 h-1 rounded-full bg-[#00A4EF]" />
                </div>
             </div>
          </motion.div>
        </motion.section>

        {/* 5. Conclusion Section */}
        <motion.section 
          className="min-h-[70vh] flex flex-col items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(5)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <motion.div 
            className="text-center px-4 max-w-2xl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ margin: "-20% 0px -20% 0px" }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-4xl md:text-5xl font-medium tracking-tight mb-6 text-black dark:text-white leading-tight">
              Unobtrusive.<br/><span className="text-[var(--text-muted)] italic">Always ready.</span>
            </h2>
            <p className="text-lg md:text-xl text-[var(--text-muted)] font-light leading-relaxed">
              Jen is designed to live quietly at the bottom of your screen, waiting for your wake word. No heavy windows, no distractions. Just raw utility.
            </p>
          </motion.div>
        </motion.section>

        {/* 5. Roadmap Section */}
        <motion.section 
          className="min-h-screen flex items-center justify-center relative z-10 py-32 bg-black/[0.01] dark:bg-black/40 border-y border-black/[0.05] dark:border-white/5 transition-colors duration-350"
          onViewportEnter={() => setActiveIdx(5)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <div className="max-w-6xl mx-auto px-6 w-full">
            <div className="text-center mb-20">
              <h2 className="text-4xl md:text-5xl font-medium tracking-tight text-black dark:text-white mb-4">What's Next</h2>
              <p className="text-lg text-black/50 dark:text-white/50">The vision for the ultimate desktop companion.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
               {/* LLM Integration - Span 4 cols */}
               <div className="md:col-span-4 bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[2.5rem] p-8 md:p-10 hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/5 dark:bg-indigo-500/10 blur-[80px] rounded-full group-hover:bg-indigo-500/10 dark:group-hover:bg-indigo-500/20 transition-colors pointer-events-none" />
                  <div className="flex items-center gap-3 mb-6 relative z-10">
                    <div className="p-3 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20 flex items-center justify-center">
                      <Cpu className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <span className="font-mono text-xs font-bold tracking-widest text-indigo-600 dark:text-indigo-400 uppercase">Intelligence</span>
                  </div>
                  <h3 className="text-2xl md:text-3xl font-semibold text-black dark:text-white mb-3 relative z-10">LLM Reasoning</h3>
                  <p className="text-black/60 dark:text-white/50 leading-relaxed max-w-lg relative z-10 mb-6">
                    Connect Jen to local models via Ollama or cloud-based LLMs for complex reasoning and natural, flowing conversations.
                  </p>
                  
                  {/* Floating visual preview */}
                  <div className="flex flex-col gap-2 rounded-2xl bg-black/[0.02] dark:bg-white/5 border border-black/[0.05] dark:border-white/10 p-4 font-mono text-[11px] text-black/50 dark:text-white/50 relative overflow-hidden h-36">
                    <div className="flex gap-2 items-center"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"/> User: hey jen, rewrite my main compiler run-loop</div>
                    <div className="flex gap-2 items-start pl-3 text-black/80 dark:text-white/80">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1"/>
                      <span>Jen: Optimizing stack layout in Rust. bundle size reduced by 14KB.</span>
                    </div>
                  </div>
               </div>

               {/* Native Rust STT - Span 2 cols */}
               <div className="md:col-span-2 bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[2.5rem] p-8 md:p-10 hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/5 dark:bg-amber-500/10 blur-[80px] rounded-full group-hover:bg-amber-500/10 dark:group-hover:bg-amber-500/20 transition-colors pointer-events-none" />
                  <div className="flex items-center gap-3 mb-6 relative z-10">
                    <div className="p-3 rounded-2xl bg-amber-50 dark:bg-amber-500/10 border border-amber-100 dark:border-amber-500/20 flex items-center justify-center">
                      <Zap className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                    </div>
                    <span className="font-mono text-xs font-bold tracking-widest text-amber-600 dark:text-amber-400 uppercase">Performance</span>
                  </div>
                  <h3 className="text-xl md:text-2xl font-semibold text-black dark:text-white mb-3">Native Rust STT</h3>
                  <p className="text-black/60 dark:text-white/50 text-[13px] leading-relaxed mb-6">
                    Migrating from Python to pure Rust for zero-latency, offline voice recognition and tiny bundle sizes.
                  </p>
                  
                  {/* Waveform graphic */}
                  <div className="flex items-center justify-between gap-1 h-12 px-4 rounded-xl bg-black/[0.02] dark:bg-white/5 border border-black/[0.05] dark:border-white/5 mt-auto">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"/>
                      <span className="font-mono text-[10px] font-semibold text-black dark:text-white">0ms offline</span>
                    </div>
                    <div className="flex gap-1 items-center h-full py-3">
                      {[1,2,3,4,3,2,4,5,4,2,3,4,3,2,1].map((val, idx) => (
                        <div key={idx} className="w-[3px] bg-amber-500/80 rounded-full" style={{ height: `${val * 20}%` }} />
                      ))}
                    </div>
                  </div>
               </div>

               {/* Context-Aware Actions - Span 2 cols */}
               <div className="md:col-span-2 bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[2.5rem] p-8 hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 dark:bg-emerald-500/10 blur-[80px] rounded-full group-hover:bg-emerald-500/10 dark:group-hover:bg-emerald-500/20 transition-colors pointer-events-none" />
                  <div className="flex items-center gap-3 mb-6 relative z-10">
                    <div className="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 flex items-center justify-center">
                      <Eye className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <span className="font-mono text-xs font-bold tracking-widest text-emerald-600 dark:text-emerald-400 uppercase">Context</span>
                  </div>
                  <h3 className="text-xl font-semibold text-black dark:text-white mb-2">Screen Context</h3>
                  <p className="text-black/60 dark:text-white/50 text-[13px] leading-relaxed mb-6">
                    Understand what is on screen to provide hyper-relevant contextual assistance.
                  </p>
                  
                  {/* Screen simulator visual */}
                  <div className="flex flex-col justify-center h-16 rounded-xl bg-black/[0.02] dark:bg-white/5 border border-black/[0.05] dark:border-white/5 p-3 relative overflow-hidden mt-auto">
                    <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[8px] font-mono text-emerald-600 dark:text-emerald-400">ACTIVE_VIEW</div>
                    <div className="w-full h-8 border border-dashed border-emerald-500/30 rounded flex items-center justify-center mt-2">
                      <span className="text-[9px] font-mono text-black/40 dark:text-white/40">Tracking window coordinate...</span>
                    </div>
                  </div>
               </div>

               {/* Calendar & Mail - Span 2 cols */}
               <div className="md:col-span-2 bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[2.5rem] p-8 hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-sky-500/5 dark:bg-sky-500/10 blur-[80px] rounded-full group-hover:bg-sky-500/10 dark:group-hover:bg-sky-500/20 transition-colors pointer-events-none" />
                  <div className="flex items-center gap-3 mb-6 relative z-10">
                    <div className="p-3 rounded-2xl bg-sky-50 dark:bg-sky-500/10 border border-sky-100 dark:border-sky-500/20 flex items-center justify-center">
                      <Calendar className="w-6 h-6 text-sky-600 dark:text-sky-400" />
                    </div>
                    <span className="font-mono text-xs font-bold tracking-widest text-sky-600 dark:text-sky-400 uppercase">OS Integrate</span>
                  </div>
                  <h3 className="text-xl font-semibold text-black dark:text-white mb-2">Productivity</h3>
                  <p className="text-black/60 dark:text-white/50 text-[13px] leading-relaxed mb-6">
                    Deep integration with native Windows calendar and mail apps for seamless scheduling.
                  </p>
                  
                  {/* Task list simulation */}
                  <div className="flex flex-col gap-2 rounded-xl bg-black/[0.02] dark:bg-white/5 border border-black/[0.05] dark:border-white/5 p-2.5 text-left mt-auto">
                    <div className="flex items-center justify-between p-1.5 rounded bg-sky-500/10 border border-sky-500/20">
                      <span className="text-[10px] font-medium text-sky-700 dark:text-sky-300">Sync Calendar</span>
                      <span className="text-[8px] font-mono text-sky-600 dark:text-sky-400">9:30 AM</span>
                    </div>
                  </div>
               </div>

               {/* Custom Skins - Span 2 cols */}
               <div className="md:col-span-2 bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[2.5rem] p-8 hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-pink-500/5 dark:bg-pink-500/10 blur-[80px] rounded-full group-hover:bg-pink-500/10 dark:group-hover:bg-pink-500/20 transition-colors pointer-events-none" />
                  <div className="flex items-center gap-3 mb-6 relative z-10">
                    <div className="p-3 rounded-2xl bg-pink-50 dark:bg-pink-500/10 border border-pink-100 dark:border-pink-500/20 flex items-center justify-center">
                      <Paintbrush className="w-6 h-6 text-pink-600 dark:text-pink-400" />
                    </div>
                    <span className="font-mono text-xs font-bold tracking-widest text-pink-600 dark:text-pink-400 uppercase">Personalize</span>
                  </div>
                  <h3 className="text-xl font-semibold text-black dark:text-white mb-2">Custom Skins</h3>
                  <p className="text-black/60 dark:text-white/50 text-[13px] leading-relaxed mb-6">
                    Personalize your companion with unique visual skins and custom interaction animations.
                  </p>
                  
                  {/* Skin selection simulator */}
                  <div className="flex gap-2.5 items-center justify-center h-10 mt-auto">
                    {['bg-gradient-to-r from-sky-400 to-indigo-500', 'bg-gradient-to-r from-pink-500 to-rose-500', 'bg-gradient-to-r from-amber-200 to-yellow-500', 'bg-gradient-to-r from-emerald-400 to-cyan-500'].map((grad, i) => (
                      <div key={i} className={`w-6 h-6 rounded-full ${grad} shadow-sm border border-white/20 hover:scale-110 transition-transform cursor-pointer`} />
                    ))}
                  </div>
               </div>
            </div>
          </div>
        </motion.section>

        {/* 6. Minimalist Download footer */}
        <motion.section 
          id="download"
          className="min-h-[75vh] flex flex-col items-center justify-center relative z-10"
          onViewportEnter={() => setActiveIdx(6)}
          viewport={{ margin: "-50% 0px -50% 0px" }}
        >
          <div className="max-w-3xl mx-auto text-center px-4">
            <h2 className="text-5xl md:text-7xl font-medium tracking-tight mb-8 text-black dark:text-white">Ready to try Jen?</h2>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center mt-12">
              <a href={downloadUrl} className="btn-primary flex items-center justify-center gap-3 py-5 px-10 text-lg">
                <Monitor className="w-5 h-5" />
                Download for Windows
              </a>
              <a href={GITHUB_URL} className="btn-secondary flex items-center justify-center gap-3 py-5 px-10 text-lg">
                <Github className="w-5 h-5" />
                View Source
              </a>
            </div>
            <p className="text-xs uppercase tracking-widest font-bold text-black/30 dark:text-white/30 mt-12">macOS Coming Soon</p>
          </div>
        </motion.section>
          </>
        ) : (
          <ChangelogView onBack={() => setView('home')} />
        )}
      </main>
    </div>
  );
}

interface ChangelogItem {
  version: string;
  date: string;
  tagline: string;
  isLatest?: boolean;
  categories: {
    title: "Features" | "Improvements" | "Bug Fixes";
    items: string[];
  }[];
}

const CHANGELOG_DATA: ChangelogItem[] = [
  {
    version: "v0.3.1b",
    date: "May 19, 2026",
    tagline: "Auto-Update Engine & Suffix Normalization",
    isLatest: true,
    categories: [
      {
        title: "Features",
        items: [
          "Auto-Update Engine: Integrated a check for updates directly into Settings, allowing you to configure updates easily.",
          "Version Manifest Check: Clients now retrieve and parse official version health details dynamically."
        ]
      },
      {
        title: "Bug Fixes",
        items: [
          "MSI Tag Compatibility: Normalized build tags by resolving a suffix naming issue to ensure Windows MSI installers compile correctly."
        ]
      }
    ]
  },
  {
    version: "v0.3",
    date: "May 19, 2026",
    tagline: "Voice Control Suite & Sensitive Command Shield",
    categories: [
      {
        title: "Features",
        items: [
          "System Control Commands: Manage screenshots, trigger clipboard actions, and launch system apps like Calculator or Paint via voice.",
          "Power Controls: Shut down, restart, hibernate, lock, or put your computer to sleep hands-free.",
          "Sensitive Command Protection: Toggle guard options in Settings to block power commands from voice activation, flashing the orb red when blocked.",
          "Screen Brightness: Added native control dependencies to easily adjust screen intensity by voice."
        ]
      },
      {
        title: "Improvements",
        items: [
          "Process Cleanup Failsafe: Reconfigured sidecar handlers to prevent orphaned background stt.exe processes after window closure.",
          "Seamless Audio Switcher: Enabled automatic audio source handovers without triggering blocker dialogue boxes."
        ]
      }
    ]
  },
  {
    version: "v0.2.11 beta",
    date: "May 10, 2026",
    tagline: "Always-Listening Wake Word & Theme Overhaul",
    categories: [
      {
        title: "Features",
        items: [
          "Voice Activation Word: Introduced support for the custom hands-free wake word ('Hey Jen') for completely offline activation.",
          "Global SUMMON Hotkey: Configure Ctrl + Shift + R to open or hide the companion window instantly from any active application."
        ]
      },
      {
        title: "Bug Fixes",
        items: [
          "OpenWakeWord Sidecar Pathing: Resolved packaging issues where critical assets and wake word templates were missing from the production directory.",
          "Type & CSS Polish: Cleaned up TS mismatches and UI style rules for a smooth launch configuration."
        ]
      }
    ]
  }
];

function ChangelogView({ onBack }: { onBack: () => void }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="max-w-4xl mx-auto px-6 pt-32 pb-48"
    >
      {/* Back Button */}
      <button
        onClick={onBack}
        className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-black/40 dark:text-white/40 hover:text-black dark:hover:text-white transition-colors mb-10 cursor-pointer border-none bg-transparent group"
      >
        <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-1 transition-transform" />
        Back to Home
      </button>

      {/* Header */}
      <div className="mb-12 text-left">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 mb-6">
          <History className="w-3.5 h-3.5 text-black/60 dark:text-white/60" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/60 dark:text-white/60">System Feed</span>
        </div>
        
        <h1 className="text-6xl md:text-7xl font-medium tracking-tight text-black dark:text-white mb-6 leading-none">
          Releases<span className="text-black/25 dark:text-white/25">.</span>
        </h1>
        
        <p className="text-lg md:text-xl text-black/50 dark:text-white/50 font-light max-w-xl leading-relaxed">
          Continuous iterations, minor details, and major upgrades. Track the engineering timeline of Jen.
        </p>
      </div>

      {/* Changelog Cards Stack */}
      <div className="space-y-12">
        {CHANGELOG_DATA.map((release) => (
          <div 
            key={release.version}
            className="bg-white dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/10 rounded-[32px] p-8 md:p-12 shadow-[0_4px_30px_rgba(0,0,0,0.01)] dark:shadow-[0_4px_30px_rgba(0,0,0,0.3)] hover:border-black/10 dark:hover:border-white/20 transition-all duration-300 relative overflow-hidden group"
          >
            {/* Subtle Gradient Glow for Latest Release */}
            {release.isLatest && (
              <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/5 blur-[80px] rounded-full pointer-events-none" />
            )}

            {/* Top Meta info */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-black/5 dark:border-white/5 pb-6 mb-8">
              <div className="flex items-center gap-3">
                <span className={`font-mono text-base font-semibold tracking-tight px-3 py-1 rounded-lg ${
                  release.isLatest 
                    ? 'bg-black dark:bg-white text-white dark:text-black' 
                    : 'bg-black/5 dark:bg-white/5 text-black/60 dark:text-white/60'
                }`}>
                  {release.version}
                </span>
                {release.isLatest && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono tracking-widest bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/15 dark:border-emerald-500/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Latest
                  </span>
                )}
              </div>
              
              <span className="font-mono text-xs text-black/35 dark:text-white/35 tracking-wider">
                {release.date}
              </span>
            </div>

            {/* Tagline */}
            <h3 className="text-3xl md:text-4xl font-medium tracking-tight text-black dark:text-white mb-8 leading-tight">
              {release.tagline}
            </h3>

            {/* Custom Monospaced Categories list */}
            <div className="space-y-6">
              {release.categories.map((cat) => {
                const getCategoryHeader = () => {
                  switch (cat.title) {
                    case "Features":
                      return (
                        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100/50 dark:border-indigo-900/30 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                          <span className="font-mono text-[10px] font-bold tracking-wider text-indigo-600 dark:text-indigo-400 uppercase">Features</span>
                        </div>
                      );
                    case "Improvements":
                      return (
                        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100/50 dark:border-emerald-900/30 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span className="font-mono text-[10px] font-bold tracking-wider text-emerald-600 dark:text-emerald-400 uppercase">Improvements</span>
                        </div>
                      );
                    case "Bug Fixes":
                      return (
                        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-100/50 dark:border-amber-900/30 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          <span className="font-mono text-[10px] font-bold tracking-wider text-amber-600 dark:text-amber-400 uppercase">Bug Fixes</span>
                        </div>
                      );
                  }
                };

                return (
                  <div key={cat.title} className="bg-black/[0.01] dark:bg-white/[0.01] border border-black/[0.04] dark:border-white/10 rounded-2xl p-6 md:p-8 space-y-6">
                    {/* Category Title Badge */}
                    {getCategoryHeader()}

                    {/* Content List */}
                    <div className="space-y-4">
                      {cat.items.map((item, itemIdx) => {
                        const parts = item.split(":");
                        if (parts.length > 1) {
                          return (
                            <div key={itemIdx} className="flex gap-3 items-start text-left text-[15px] leading-relaxed border-b border-black/[0.03] dark:border-white/[0.03] pb-4 last:border-0 last:pb-0">
                              <span className="text-black/30 dark:text-white/30 select-none mt-1 font-mono text-xs">—</span>
                              <div>
                                <span className="font-semibold text-black dark:text-white tracking-tight">{parts[0]}</span>
                                <span className="text-black/65 dark:text-white/65">: {parts.slice(1).join(":")}</span>
                              </div>
                            </div>
                          );
                        }
                        return (
                          <div key={itemIdx} className="flex gap-3 items-start text-left text-[15px] leading-relaxed text-black/65 dark:text-white/65 border-b border-black/[0.03] dark:border-white/[0.03] pb-4 last:border-0 last:pb-0">
                            <span className="text-black/30 dark:text-white/30 select-none mt-1 font-mono text-xs">—</span>
                            <span>{item}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

          </div>
        ))}
      </div>
    </motion.div>
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
