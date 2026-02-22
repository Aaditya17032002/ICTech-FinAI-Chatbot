import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { 
  Copy, User, Bot, Check, ChevronDown, ChevronUp, ExternalLink, 
  AlertTriangle, Send, Loader2, X, Building2, PieChart, Wallet, 
  Percent, TrendingUp, Calendar, ChevronRight, TrendingDown, Activity
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessageData, InvestmentResponse, DataPoint, Source, Fund, FundDetail } from "../types";
import { cn } from "../cn";

// --- MarketPulse (Thinking Indicator) ---
export const MarketPulse: React.FC = () => {
  const insights = [
    "Analyzing market volatility...",
    "Comparing expense ratios...",
    "Evaluating historical CAGR...",
    "Checking AUM trends...",
    "Scanning risk profiles...",
    "Optimizing portfolio insights..."
  ];
  const [insightIdx, setInsightIdx] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setInsightIdx((prev) => (prev + 1) % insights.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 space-y-6">
      <div className="relative w-64 h-32 bg-zinc-100/50 dark:bg-zinc-900/50 rounded-3xl border border-zinc-200/50 dark:border-zinc-800/50 overflow-hidden flex items-center justify-center">
        <div className="absolute inset-0 opacity-20">
          <svg viewBox="0 0 200 100" className="w-full h-full">
            <motion.path
              d="M0 80 Q 20 20, 40 50 T 80 30 T 120 70 T 160 40 T 200 60"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-emerald-500"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
          </svg>
        </div>
        <Activity size={32} className="text-emerald-500 animate-pulse" />
      </div>
      
      <div className="flex flex-col items-center space-y-2">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{ scale: [1, 1.5, 1], opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
              className="w-1.5 h-1.5 rounded-full bg-emerald-500"
            />
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.p
            key={insightIdx}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="text-xs font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-500"
          >
            {insights[insightIdx]}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
};

// --- DataPointsCard ---
interface DataPointsCardProps {
  dataPoints: DataPoint[];
}

export const DataPointsCard: React.FC<DataPointsCardProps> = ({ dataPoints }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 my-6">
      {dataPoints.map((dp, idx) => (
        <motion.div 
          key={idx} 
          whileHover={{ y: -4 }}
          className="group relative bg-white/40 dark:bg-zinc-900/40 backdrop-blur-md border border-zinc-200/50 dark:border-zinc-800/50 rounded-2xl p-5 shadow-sm hover:shadow-xl hover:border-emerald-500/30 transition-all duration-300"
        >
          <div className="absolute top-0 right-0 p-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <TrendingUp size={14} className="text-emerald-500" />
          </div>
          <div className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest mb-2">
            {dp.metric}
          </div>
          <div className="text-2xl font-black text-zinc-900 dark:text-zinc-100 tracking-tight">
            {dp.value}
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 mt-3 font-medium">
            <Calendar size={10} />
            Updated {dp.as_of_date}
          </div>
        </motion.div>
      ))}
    </div>
  );
};

// --- SourcesList ---
interface SourcesListProps {
  sources: Source[];
}

export const SourcesList: React.FC<SourcesListProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-4 border-t border-zinc-100 dark:border-zinc-800 pt-4">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs font-semibold text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors uppercase tracking-widest"
      >
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        Sources ({sources.length})
      </button>
      
      {isOpen && (
        <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
          {sources.map((source, idx) => (
            <a 
              key={idx}
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-2 rounded-lg bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-100 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-600 transition-all group"
            >
              <div className="flex flex-col">
                <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{source.name}</span>
                <span className="text-[10px] text-zinc-400">Accessed {new Date(source.accessed_at).toLocaleDateString()}</span>
              </div>
              <ExternalLink size={14} className="text-zinc-400 group-hover:text-zinc-900 dark:group-hover:text-zinc-100" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

// --- RiskDisclaimer ---
interface RiskDisclaimerProps {
  text: string;
}

export const RiskDisclaimer: React.FC<RiskDisclaimerProps> = ({ text }) => {
  return (
    <div className="mt-6 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/30 flex gap-3">
      <AlertTriangle size={18} className="text-amber-600 dark:text-amber-500 shrink-0 mt-0.5" />
      <p className="text-xs leading-relaxed text-amber-800 dark:text-amber-200/80 italic">
        {text}
      </p>
    </div>
  );
};

// --- ChatMessage ---
interface ChatMessageProps {
  message: ChatMessageData;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [copied, setCopied] = React.useState(false);
  const isBot = message.role === "bot";
  const content = message.content;

  const handleCopy = () => {
    const textToCopy = typeof content === "string" ? content : content.explanation;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: isBot ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "flex w-full gap-4 py-10 px-4 sm:px-6 border-b border-zinc-100/50 dark:border-zinc-900/50",
        isBot ? "bg-zinc-50/30 dark:bg-zinc-900/20" : "bg-transparent"
      )}
    >
      <div className="max-w-4xl mx-auto flex w-full gap-4 sm:gap-8">
        <div className={cn(
          "w-10 h-10 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center shrink-0 border shadow-lg transition-transform hover:scale-105",
          isBot 
            ? "bg-zinc-900 border-zinc-800 text-white dark:bg-white dark:text-zinc-900 dark:border-zinc-200" 
            : "bg-white border-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-300"
        )}>
          {isBot ? <Bot size={20} /> : <User size={20} />}
        </div>

        <div className="flex-1 min-w-0 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-400 dark:text-zinc-500">
                {isBot ? "FinAI Intelligence" : "Investor"}
              </span>
              {isBot && (
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 text-[8px] font-black uppercase tracking-widest">
                  Verified Data
                </span>
              )}
            </div>
            {isBot && !message.isStreaming && (
              <button 
                onClick={handleCopy}
                className="p-2 rounded-xl hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all"
              >
                {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
              </button>
            )}
          </div>

          <div className="prose prose-zinc dark:prose-invert max-w-none text-zinc-800 dark:text-zinc-200 leading-relaxed text-lg font-medium">
            {typeof content === "string" ? (
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-4 rounded-xl border border-zinc-200 dark:border-zinc-700">
                      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-700">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-zinc-100 dark:bg-zinc-800">{children}</thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700 bg-white dark:bg-zinc-900">{children}</tbody>
                  ),
                  tr: ({ children }) => (
                    <tr className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">{children}</tr>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100 whitespace-nowrap">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 whitespace-nowrap">{children}</td>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            ) : (
              <>
                <div className="mb-6">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-4 rounded-xl border border-zinc-200 dark:border-zinc-700">
                          <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-700">
                            {children}
                          </table>
                        </div>
                      ),
                      thead: ({ children }) => (
                        <thead className="bg-zinc-100 dark:bg-zinc-800">{children}</thead>
                      ),
                      tbody: ({ children }) => (
                        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700 bg-white dark:bg-zinc-900">{children}</tbody>
                      ),
                      tr: ({ children }) => (
                        <tr className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">{children}</tr>
                      ),
                      th: ({ children }) => (
                        <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100 whitespace-nowrap">{children}</th>
                      ),
                      td: ({ children }) => (
                        <td className="px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 whitespace-nowrap">{children}</td>
                      ),
                    }}
                  >
                    {content.explanation}
                  </ReactMarkdown>
                </div>
                <DataPointsCard dataPoints={content.data_points} />
                <SourcesList sources={content.sources} />
                <RiskDisclaimer text={content.risk_disclaimer} />
              </>
            )}
            {message.isStreaming && (
              <motion.span 
                animate={{ opacity: [0, 1, 0] }}
                transition={{ duration: 0.8, repeat: Infinity }}
                className="inline-block w-2 h-5 ml-1 bg-emerald-500 align-middle rounded-sm" 
              />
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// --- ChatInput ---
interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading }) => {
  const [input, setInput] = useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput("");
    }
  };

  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-xl p-4 sm:p-6">
      <form 
        onSubmit={handleSubmit}
        className="max-w-4xl mx-auto relative flex items-end gap-2"
      >
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about mutual funds, comparisons, or market trends..."
            className="w-full bg-zinc-100 dark:bg-zinc-900 border-none rounded-2xl py-3 px-4 pr-12 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 focus:ring-2 focus:ring-zinc-900 dark:focus:ring-zinc-100 resize-none transition-all min-h-[48px]"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={cn(
              "absolute right-2 bottom-2 p-2 rounded-xl transition-all",
              input.trim() && !isLoading 
                ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" 
                : "bg-zinc-200 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-600 cursor-not-allowed"
            )}
          >
            {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
      </form>
      <p className="text-[10px] text-center text-zinc-400 mt-3 uppercase tracking-widest font-medium">
        FinAI can make mistakes. Check important info.
      </p>
    </div>
  );
};

// --- FundCard ---
interface FundCardProps {
  fund: Fund;
  onClick: (fund: Fund) => void;
}

export const FundCard: React.FC<FundCardProps> = ({ fund, onClick }) => {
  return (
    <div 
      onClick={() => onClick(fund)}
      className="group bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm hover:shadow-xl hover:border-zinc-400 dark:hover:border-zinc-600 transition-all cursor-pointer flex flex-col justify-between"
    >
      <div>
        <div className="flex justify-between items-start mb-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
            {fund.category || "Mutual Fund"}
          </span>
          <TrendingUp size={16} className="text-emerald-500" />
        </div>
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 leading-tight mb-2 group-hover:text-zinc-700 dark:group-hover:text-zinc-300 transition-colors">
          {fund.scheme_name}
        </h3>
      </div>
      
      <div className="mt-6 flex items-end justify-between">
        <div className="space-y-1">
          <div className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Current NAV</div>
          <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            {fund.nav ? `₹${fund.nav.toLocaleString()}` : "N/A"}
          </div>
          {fund.nav_date && (
            <div className="flex items-center gap-1 text-[10px] text-zinc-400">
              <Calendar size={10} />
              {fund.nav_date}
            </div>
          )}
        </div>
        <div className="w-10 h-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center group-hover:bg-zinc-900 group-hover:text-white dark:group-hover:bg-white dark:group-hover:text-zinc-900 transition-all">
          <ChevronRight size={20} />
        </div>
      </div>
    </div>
  );
};

// --- FundDetailModal ---
interface FundDetailModalProps {
  fund: FundDetail | null;
  isOpen: boolean;
  onClose: () => void;
  isLoading?: boolean;
}

export const FundDetailModal: React.FC<FundDetailModalProps> = ({ fund, isOpen, onClose, isLoading = false }) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6">
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-zinc-950/60 backdrop-blur-sm"
          />
          
          <motion.div 
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-2xl bg-white dark:bg-zinc-900 rounded-3xl shadow-2xl overflow-hidden border border-zinc-200 dark:border-zinc-800"
          >
            {isLoading ? (
              <div className="p-12 flex flex-col items-center justify-center">
                <Loader2 size={48} className="animate-spin text-zinc-400 mb-4" />
                <p className="text-sm text-zinc-500 font-medium">Loading fund details...</p>
              </div>
            ) : !fund ? (
              <div className="p-12 flex flex-col items-center justify-center">
                <p className="text-sm text-zinc-500 font-medium">Fund not found</p>
                <button onClick={onClose} className="mt-4 px-4 py-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg text-sm font-medium">
                  Close
                </button>
              </div>
            ) : (
              <>
            <div className="p-6 sm:p-8 border-b border-zinc-100 dark:border-zinc-800 flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-2 block">
                  {fund.category}
                </span>
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 leading-tight">
                  {fund.scheme_name}
                </h2>
              </div>
              <button 
                onClick={onClose}
                className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all"
              >
                <X size={24} />
              </button>
            </div>

            <div className="p-6 sm:p-8 overflow-y-auto max-h-[70vh]">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mb-10">
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                    <Building2 size={14} /> Fund House
                  </div>
                  <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{fund.fund_house || "N/A"}</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                    <Wallet size={14} /> AUM
                  </div>
                  <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{fund.aum || "N/A"}</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                    <Percent size={14} /> Exp. Ratio
                  </div>
                  <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{fund.expense_ratio || "N/A"}</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                    <TrendingUp size={14} /> NAV
                  </div>
                  <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{fund.nav ? `₹${fund.nav}` : "N/A"}</div>
                </div>
              </div>

              <div className="space-y-6">
                <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 flex items-center gap-2">
                  <PieChart size={16} /> Performance Returns
                </h3>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-4">
                  {Object.entries(fund.returns).map(([period, value]) => (
                    <div key={period} className="bg-zinc-50 dark:bg-zinc-800/50 p-3 rounded-xl border border-zinc-100 dark:border-zinc-800 text-center">
                      <div className="text-[10px] font-bold uppercase text-zinc-400 mb-1">{period}</div>
                      <div className={cn(
                        "text-sm font-bold",
                        value.startsWith("-") ? "text-rose-500" : "text-emerald-500"
                      )}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-10 p-5 rounded-2xl bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 flex items-center justify-between">
                <div>
                  <div className="text-xs font-medium opacity-70">Ready to invest?</div>
                  <div className="text-lg font-bold">Start a SIP today</div>
                </div>
                <button className="bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-2 rounded-xl font-bold transition-all">
                  Invest Now
                </button>
              </div>
            </div>
            </>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
