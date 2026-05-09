import React from "react";
import ReactDOM from "react-dom/client";
import { motion } from "framer-motion";
import { Orb } from "./components/Orb";
import { 
  Download, 
  Cpu, 
  Mic, 
  Zap, 
  ArrowRight,
  Monitor,
  Layout,
  MousePointer2
} from "lucide-react";
import "./Website.css";

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
  return (
    <div className="min-h-screen relative overflow-x-hidden">
      <div className="grain-overlay" />
      
      {/* Navigation */}
      <nav className="glass-nav">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-black flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-white" />
          </div>
          <span className="font-medium tracking-tight">jen</span>
        </div>
        <div className="flex items-center gap-6 text-sm font-medium">
          <a href="#features" className="text-[var(--text-muted)] hover:text-black transition-colors">Features</a>
          <a href={GITHUB_URL} className="flex items-center gap-1.5 text-[var(--text-muted)] hover:text-black transition-colors">
            <Github className="w-4 h-4" />
            GitHub
          </a>
          <a href="#download" className="btn-primary py-2 px-5 text-xs">Download</a>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-48 pb-24 px-8 max-w-7xl mx-auto flex flex-col items-center">
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

        <motion.div 
          className="orb-container"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.2, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="orb-glow" />
          <Orb 
            className="w-full h-full" 
            colors={["#f8fafc", "#94a3b8"]} 
            agentState="thinking"
          />
        </motion.div>

        <motion.div
          className="flex flex-col md:flex-row gap-4 mt-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <a href="#download" className="btn-primary flex items-center gap-2">
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
      <section className="py-24 px-8 bg-[#F2F2F7]/50">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
            <div className="space-y-6">
              <h2 className="text-4xl font-medium tracking-tight">Always there, never in the way.</h2>
              <p className="text-lg text-[var(--text-muted)] font-light leading-relaxed">
                Jen isn't just another app window. It's an ambient presence on your screen that responds to your voice and helps you navigate your digital life without breaking your flow.
              </p>
              <ul className="space-y-4">
                {[
                  { icon: MousePointer2, text: "Click-through transparency" },
                  { icon: Layout, text: "Lives in the corner of your eye" },
                  { icon: Monitor, text: "Cross-platform consistency" }
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-sm font-medium">
                    <item.icon className="w-5 h-5 opacity-40" />
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>
            <div className="soft-tech-card p-1 aspect-video flex items-center justify-center overflow-hidden bg-slate-200">
               {/* Mockup of a desktop environment */}
               <div className="w-full h-full bg-[#1d1d1f] rounded-[1.4rem] relative p-4 flex items-end justify-end">
                  <div className="absolute top-4 left-4 flex gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-red-500/50" />
                    <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                    <div className="w-2 h-2 rounded-full bg-green-500/50" />
                  </div>
                  <div className="w-16 h-16 mr-2 mb-2">
                     <Orb colors={["#bae6fd", "#38bdf8"]} agentState="listening" className="w-full h-full" />
                  </div>
                  <div className="absolute inset-0 flex items-center justify-center opacity-10">
                     <Monitor className="w-32 h-32" />
                  </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="feature-grid">
        <div className="feature-item">
          <Mic className="feature-icon" />
          <h3 className="feature-title">Voice First</h3>
          <p className="feature-desc">Natural language processing that understands your intent, not just your words.</p>
        </div>
        <div className="feature-item">
          <Cpu className="feature-icon" />
          <h3 className="feature-title">Local Intelligence</h3>
          <p className="feature-desc">Fast, secure, and private. Much of Jen's processing happens right on your machine.</p>
        </div>
        <div className="feature-item">
          <Zap className="feature-icon" />
          <h3 className="feature-title">Instant Response</h3>
          <p className="feature-desc">Zero friction. Activate with a hotkey or voice and get what you need instantly.</p>
        </div>
      </section>

      {/* Download Section */}
      <section id="download" className="py-32 px-8 flex flex-col items-center bg-black text-white">
        <h2 className="text-5xl font-medium tracking-tight mb-16 text-center">Ready to meet Jen?</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
          {[
            { platform: "Windows", ext: ".exe / .msi", icon: "🪟" },
            { platform: "macOS", ext: ".dmg / .app", icon: "🍎" },
            { platform: "Linux", ext: ".deb / .AppImage", icon: "🐧" }
          ].map((p) => (
            <a 
              key={p.platform} 
              href={RELEASES_URL}
              className="group p-8 rounded-3xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all flex flex-col items-center gap-4 text-center"
            >
              <span className="text-4xl">{p.icon}</span>
              <div>
                <h4 className="font-medium text-lg">{p.platform}</h4>
                <p className="text-xs text-white/40 mt-1">{p.ext}</p>
              </div>
              <Download className="w-5 h-5 mt-4 opacity-40 group-hover:opacity-100 transition-opacity" />
            </a>
          ))}
        </div>

        <p className="mt-12 text-white/40 text-sm flex items-center gap-2">
          <Github className="w-4 h-4" />
          Open source on GitHub
        </p>
      </section>

      {/* Footer */}
      <footer className="py-12 px-8 border-t border-[#e8e8ed] text-center">
        <p className="text-sm text-[var(--text-muted)]">
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
