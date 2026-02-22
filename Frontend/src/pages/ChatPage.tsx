import React, { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { Trash2, Sparkles, AlertCircle, RefreshCcw, TrendingUp, TrendingDown } from "lucide-react";
import { ChatMessage, MarketPulse } from "../components/UIComponents";
import { ChatInput } from "../components/UIComponents";
import { ChatMessageData, InvestmentResponse } from "../types";
import { api, streamChatFetch } from "../services/api";
import { motion, AnimatePresence } from "motion/react";

interface TickerItem {
  name: string;
  value: string;
  change: string;
  up: boolean;
}

const MarketTicker: React.FC = () => {
  const [tickerData, setTickerData] = useState<TickerItem[]>([
    { name: "NIFTY 50", value: "Loading...", change: "0.00%", up: true },
    { name: "SENSEX", value: "Loading...", change: "0.00%", up: true },
  ]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTickerData = async () => {
      try {
        const data = await api.getMarketTicker();
        if (data.items && data.items.length > 0) {
          setTickerData(data.items.map(item => ({
            name: item.name,
            value: item.value,
            change: item.change,
            up: item.up,
          })));
        }
      } catch (err) {
        console.error("Failed to fetch ticker data:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTickerData();
    const interval = setInterval(fetchTickerData, 60000);
    return () => clearInterval(interval);
  }, []);

  const displayData = tickerData.length > 0 ? [...tickerData, ...tickerData] : [];

  return (
    <div className="w-full bg-zinc-900 text-white py-1.5 overflow-hidden whitespace-nowrap border-b border-white/5">
      <motion.div 
        animate={{ x: [0, -1000] }}
        transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
        className="inline-flex gap-12"
      >
        {displayData.map((s, i) => (
          <div key={i} className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-widest">
            <span className="text-zinc-500">{s.name}</span>
            <span>{s.value}</span>
            <span className={s.up ? "text-emerald-400" : "text-rose-400"}>
              {s.up ? <TrendingUp size={10} className="inline mr-1" /> : <TrendingDown size={10} className="inline mr-1" />}
              {s.change}
            </span>
          </div>
        ))}
      </motion.div>
    </div>
  );
};

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const savedSession = localStorage.getItem("session_id");
    const savedMessages = localStorage.getItem("chat_history");
    
    if (savedSession) setSessionId(savedSession);
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch (e) {
        console.error("Failed to load history", e);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("chat_history", JSON.stringify(messages));
    if (sessionId) localStorage.setItem("session_id", sessionId);
    scrollToBottom();
  }, [messages, sessionId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const clearChat = async () => {
    try {
      // Clear server-side cache
      await api.resetApplication();
      console.log("[ChatPage] Server cache cleared");
    } catch (err) {
      console.error("[ChatPage] Failed to clear server cache:", err);
    }
    
    // Clear client-side state
    setMessages([]);
    setSessionId(null);
    setError(null);
    
    // Clear all localStorage
    localStorage.removeItem("chat_history");
    localStorage.removeItem("session_id");
    localStorage.removeItem("user_profile");
    
    // Generate new session ID for fresh start
    const newSessionId = uuidv4();
    setSessionId(newSessionId);
    localStorage.setItem("session_id", newSessionId);
  };

  const handleSend = async (text: string, forceStatic: boolean = false) => {
    const userMsg: ChatMessageData = {
      id: uuidv4(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    if (!forceStatic && (text.toLowerCase().includes("compare") || text.toLowerCase().includes("vs"))) {
      await handleStreamingResponse(text);
    } else {
      await handleNormalResponse(text);
    }
  };

  const handleNormalResponse = async (text: string) => {
    try {
      const data = await api.chat(text, sessionId);
      if (!sessionId) setSessionId(data.session_id);
      
      const botMsg: ChatMessageData = {
        id: uuidv4(),
        role: "bot",
        content: data.response,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setError("Failed to get response. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStreamingResponse = async (text: string) => {
    const botMsgId = uuidv4();
    const initialBotMsg: ChatMessageData = {
      id: botMsgId,
      role: "bot",
      content: "",
      timestamp: Date.now(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, initialBotMsg]);

    try {
      let fullExplanation = "";
      let finalData: any = null;

      for await (const chunk of streamChatFetch(text, sessionId)) {
        if (chunk.token) {
          fullExplanation += chunk.token;
          setMessages((prev) => 
            prev.map((m) => 
              m.id === botMsgId ? { ...m, content: fullExplanation } : m
            )
          );
        }
        if (chunk.response) {
          finalData = chunk.response;
          if (!sessionId) setSessionId(chunk.session_id);
        }
      }

      if (finalData) {
        setMessages((prev) => 
          prev.map((m) => 
            m.id === botMsgId ? { ...m, content: finalData, isStreaming: false } : m
          )
        );
      }
    } catch (err) {
      setError("Streaming failed. Please try again.");
      setMessages((prev) => prev.filter(m => m.id !== botMsgId));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-zinc-950">
      <MarketTicker />
      {/* Header */}
      <header className="h-20 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-6 shrink-0 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-zinc-900 dark:bg-white rounded-2xl flex items-center justify-center shadow-xl">
            <Sparkles size={20} className="text-white dark:text-zinc-900" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-zinc-900 dark:text-zinc-100 leading-none mb-1">FinAI Intelligence</h1>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Systems Online</span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button 
              onClick={clearChat}
              className="flex items-center gap-2 px-4 py-2 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] text-zinc-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-all border border-transparent hover:border-rose-200 dark:hover:border-rose-900/50"
            >
              <Trash2 size={14} />
              Reset Session
            </button>
          )}
        </div>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto scrollbar-hide">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-6 text-center max-w-3xl mx-auto">
            <motion.div 
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-24 h-24 bg-zinc-100 dark:bg-zinc-900 rounded-[2.5rem] flex items-center justify-center mb-8 shadow-inner"
            >
              <Sparkles size={48} className="text-zinc-400 dark:text-zinc-600" />
            </motion.div>
            <h2 className="text-4xl sm:text-5xl font-black text-zinc-900 dark:text-zinc-100 mb-6 tracking-tight leading-tight">
              The Future of <span className="text-zinc-400">Wealth</span> is Here.
            </h2>
            <p className="text-zinc-500 dark:text-zinc-400 mb-12 text-lg leading-relaxed max-w-xl">
              Your institutional-grade investment advisor, powered by advanced AI. Start by asking a question or selecting a prompt below.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
              {[
                "What are top performing mutual funds?",
                "Compare SBI Bluechip vs HDFC Top 100",
                "Explain expense ratio in simple terms",
                "Best large cap funds for 5 year horizon"
              ].map((suggestion, idx) => (
                <motion.button 
                  key={idx}
                  whileHover={{ scale: 1.02, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleSend(suggestion, true)}
                  className="p-5 rounded-3xl border border-zinc-200 dark:border-zinc-800 text-left text-sm font-bold text-zinc-700 dark:text-zinc-300 hover:border-zinc-900 dark:hover:border-zinc-100 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-all shadow-sm hover:shadow-xl"
                >
                  {suggestion}
                </motion.button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isLoading && !messages.some(m => m.isStreaming) && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="max-w-4xl mx-auto w-full"
              >
                <MarketPulse />
              </motion.div>
            )}
            <div ref={messagesEndRef} className="h-4" />
          </div>
        )}

        <AnimatePresence>
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="fixed bottom-32 left-1/2 -translate-x-1/2 w-full max-w-md px-4 z-20"
            >
              <div className="bg-rose-50/80 dark:bg-rose-950/80 backdrop-blur-xl border border-rose-200 dark:border-rose-900/50 p-5 rounded-3xl flex items-center justify-between shadow-2xl">
                <div className="flex items-center gap-3 text-rose-800 dark:text-rose-200">
                  <AlertCircle size={20} />
                  <span className="text-sm font-bold">{error}</span>
                </div>
                <button 
                  onClick={() => handleSend(messages[messages.length - 1].content as string)}
                  className="p-2.5 rounded-2xl bg-rose-100 dark:bg-rose-900/50 text-rose-800 dark:text-rose-200 hover:bg-rose-200 dark:hover:bg-rose-800 transition-all"
                >
                  <RefreshCcw size={18} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Input */}
      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </div>
  );
};
