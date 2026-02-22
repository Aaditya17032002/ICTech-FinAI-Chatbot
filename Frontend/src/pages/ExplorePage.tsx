import React, { useState, useEffect } from "react";
import { Search, Loader2, Compass, ArrowRight } from "lucide-react";
import { FundCard, FundDetailModal } from "../components/UIComponents";
import { Fund, FundDetail } from "../types";
import { api } from "../services/api";
import { motion } from "motion/react";

export const ExplorePage: React.FC = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Fund[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFund, setSelectedFund] = useState<FundDetail | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      handleSearch();
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [query]);

  const handleSearch = async () => {
    setIsLoading(true);
    try {
      const data = await api.searchFunds(query);
      setResults(data.results);
    } catch (err) {
      console.error("Search failed", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFundClick = async (fund: Fund) => {
    setIsModalOpen(true);
    setIsModalLoading(true);
    setSelectedFund(null);
    
    try {
      const detail = await api.getFundDetail(fund.scheme_code);
      setSelectedFund(detail);
    } catch (err) {
      console.error("Failed to fetch detail", err);
      setIsModalOpen(false);
    } finally {
      setIsModalLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 pb-20">
      {/* Hero Section */}
      <section className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 pt-20 pb-12 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 text-[10px] font-bold uppercase tracking-widest mb-6"
          >
            <Compass size={14} /> Explore Funds
          </motion.div>
          <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-100 mb-6 tracking-tight">
            Find the perfect fund for your goals.
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 max-w-2xl mx-auto text-lg mb-10 leading-relaxed">
            Search through thousands of mutual funds across categories. Analyze performance, risk metrics, and expense ratios in one place.
          </p>

          <div className="max-w-2xl mx-auto relative group">
            <div className="absolute inset-0 bg-zinc-900/5 dark:bg-white/5 blur-2xl group-hover:bg-zinc-900/10 dark:group-hover:white/10 transition-all rounded-full" />
            <div className="relative flex items-center">
              <Search className="absolute left-5 text-zinc-400" size={20} />
              <input 
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by fund name, category, or AMC..."
                className="w-full h-16 bg-white dark:bg-zinc-900 border-2 border-zinc-100 dark:border-zinc-800 rounded-2xl pl-14 pr-6 text-lg text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-900 dark:focus:border-zinc-100 focus:ring-0 transition-all shadow-xl"
              />
              {isLoading && (
                <Loader2 className="absolute right-5 text-zinc-400 animate-spin" size={20} />
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Results Section */}
      <main className="max-w-6xl mx-auto px-6 mt-12">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-500">
            {query ? `Search Results (${results.length})` : "Popular Funds"}
          </h2>
          <div className="flex gap-2">
            {["Equity", "Debt", "Hybrid", "Index"].map(cat => (
              <button 
                key={cat}
                onClick={() => setQuery(cat)}
                className="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:border-zinc-900 dark:hover:border-zinc-100 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all"
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {results.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {results.map((fund, idx) => (
              <motion.div
                key={fund.scheme_code}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <FundCard fund={fund} onClick={handleFundClick} />
              </motion.div>
            ))}
          </div>
        ) : !isLoading && (
          <div className="text-center py-20 bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-100 dark:border-zinc-800">
            <div className="w-16 h-16 bg-zinc-50 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4">
              <Search size={24} className="text-zinc-300" />
            </div>
            <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">No funds found</h3>
            <p className="text-zinc-500 dark:text-zinc-400">Try searching for something else like "SBI" or "Large Cap"</p>
          </div>
        )}
      </main>

      {/* Detail Modal */}
      <FundDetailModal 
        fund={selectedFund}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        isLoading={isModalLoading}
      />

      {/* Bottom CTA - Hidden on mobile/tablet since we have navigation */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30 hidden lg:block">
        <a 
          href="/"
          className="flex items-center gap-3 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 px-8 py-4 rounded-2xl font-bold shadow-2xl hover:scale-105 transition-all group"
        >
          Back to AI Advisor
          <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
        </a>
      </div>
    </div>
  );
};
