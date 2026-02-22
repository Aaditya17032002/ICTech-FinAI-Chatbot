import React from "react";
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from "react-router-dom";
import { ChatPage } from "./pages/ChatPage";
import { ExplorePage } from "./pages/ExplorePage";
import { useDarkMode } from "./hooks/useDarkMode";
import { Moon, Sun, Compass, MessageSquare } from "lucide-react";
import { cn } from "./cn";

function Navigation() {
  const location = useLocation();
  const { isDark, toggle } = useDarkMode();

  return (
    <nav className="fixed left-6 top-1/2 -translate-y-1/2 z-50 hidden lg:flex flex-col gap-4 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-xl border border-zinc-200 dark:border-zinc-800 p-2 rounded-2xl shadow-2xl">
      <Link 
        to="/" 
        className={cn(
          "p-3 rounded-xl transition-all",
          location.pathname === "/" 
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" 
            : "text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
        )}
        title="AI Advisor"
      >
        <MessageSquare size={24} />
      </Link>
      <Link 
        to="/explore" 
        className={cn(
          "p-3 rounded-xl transition-all",
          location.pathname === "/explore" 
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" 
            : "text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
        )}
        title="Explore Funds"
      >
        <Compass size={24} />
      </Link>
      <div className="h-px bg-zinc-200 dark:bg-zinc-800 mx-2 my-1" />
      <button 
        onClick={toggle}
        className="p-3 rounded-xl text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all"
        title="Toggle Theme"
      >
        {isDark ? <Sun size={24} /> : <Moon size={24} />}
      </button>
    </nav>
  );
}

function MobileNav() {
  const location = useLocation();
  const { isDark, toggle } = useDarkMode();
  
  // Hide mobile nav on chat page to avoid overlapping with chat input
  const isChatPage = location.pathname === "/";

  return (
    <nav className={cn(
      "fixed left-1/2 -translate-x-1/2 z-50 flex lg:hidden items-center gap-2 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-xl border border-zinc-200 dark:border-zinc-800 p-2 rounded-2xl shadow-2xl transition-all",
      isChatPage ? "top-24" : "bottom-6"
    )}>
      <Link 
        to="/" 
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-xl transition-all font-bold text-xs uppercase tracking-widest",
          location.pathname === "/" 
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" 
            : "text-zinc-400"
        )}
      >
        <MessageSquare size={18} />
        {location.pathname === "/" && "Chat"}
      </Link>
      <Link 
        to="/explore" 
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-xl transition-all font-bold text-xs uppercase tracking-widest",
          location.pathname === "/explore" 
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" 
            : "text-zinc-400"
        )}
      >
        <Compass size={18} />
        {location.pathname === "/explore" && "Explore"}
      </Link>
      <button 
        onClick={toggle}
        className="p-2 rounded-xl text-zinc-400"
      >
        {isDark ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    </nav>
  );
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-white dark:bg-zinc-950 transition-colors duration-300">
        <Navigation />
        <MobileNav />
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/explore" element={<ExplorePage />} />
        </Routes>
      </div>
    </Router>
  );
}
