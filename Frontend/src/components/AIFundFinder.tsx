import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { 
  Sparkles, Target, Clock, TrendingUp, Shield, Zap, 
  ChevronRight, ChevronLeft, Loader2, X, RefreshCcw,
  Wallet, PiggyBank, Home, GraduationCap, Plane
} from "lucide-react";
import { api } from "../services/api";
import { Fund } from "../types";

interface AIFundFinderProps {
  onFundSelect: (fund: Fund) => void;
  onClose: () => void;
}

type Step = "welcome" | "goal" | "risk" | "horizon" | "amount" | "loading" | "results";

interface UserPreferences {
  goal: string;
  riskTolerance: "conservative" | "moderate" | "aggressive";
  investmentHorizon: "short_term" | "medium_term" | "long_term";
  monthlyAmount: number;
}

const goals = [
  { id: "wealth", label: "Wealth Creation", icon: TrendingUp, description: "Long-term growth" },
  { id: "retirement", label: "Retirement", icon: PiggyBank, description: "Secure future" },
  { id: "tax_saving", label: "Tax Saving", icon: Shield, description: "Save on taxes" },
  { id: "house", label: "Buy a House", icon: Home, description: "Down payment" },
  { id: "education", label: "Education", icon: GraduationCap, description: "Child's future" },
  { id: "travel", label: "Travel/Vacation", icon: Plane, description: "Dream trip" },
];

const riskOptions = [
  { id: "conservative", label: "Conservative", icon: Shield, description: "Low risk, stable returns", color: "emerald" },
  { id: "moderate", label: "Moderate", icon: Target, description: "Balanced risk-reward", color: "amber" },
  { id: "aggressive", label: "Aggressive", icon: Zap, description: "High risk, high returns", color: "rose" },
];

const horizonOptions = [
  { id: "short_term", label: "1-3 Years", description: "Short term goals" },
  { id: "medium_term", label: "3-5 Years", description: "Medium term planning" },
  { id: "long_term", label: "5+ Years", description: "Long term wealth" },
];

export const AIFundFinder: React.FC<AIFundFinderProps> = ({ onFundSelect, onClose }) => {
  const [step, setStep] = useState<Step>("welcome");
  const [preferences, setPreferences] = useState<UserPreferences>({
    goal: "",
    riskTolerance: "moderate",
    investmentHorizon: "medium_term",
    monthlyAmount: 5000,
  });
  const [recommendations, setRecommendations] = useState<Fund[]>([]);
  const [aiInsight, setAiInsight] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  const getRecommendations = async () => {
    setStep("loading");
    setIsLoading(true);

    try {
      // Build a smart query based on user preferences
      let category = "";
      let query = "";

      // Map goal to category
      if (preferences.goal === "tax_saving") {
        category = "ELSS";
        query = "ELSS tax saving";
      } else if (preferences.riskTolerance === "conservative") {
        if (preferences.investmentHorizon === "short_term") {
          category = "debt";
          query = "liquid debt fund";
        } else {
          category = "large cap";
          query = "large cap bluechip";
        }
      } else if (preferences.riskTolerance === "aggressive") {
        if (preferences.investmentHorizon === "long_term") {
          category = "small cap";
          query = "small cap growth";
        } else {
          category = "mid cap";
          query = "mid cap";
        }
      } else {
        // Moderate
        if (preferences.investmentHorizon === "long_term") {
          category = "flexi cap";
          query = "flexi cap multi cap";
        } else {
          category = "large cap";
          query = "large cap";
        }
      }

      // Get fund recommendations
      const searchResult = await api.searchFunds(query, 6);
      setRecommendations(searchResult.results || []);

      // Get AI insight using chat API
      const insightQuery = `Based on a ${preferences.riskTolerance} risk tolerance, ${preferences.investmentHorizon.replace("_", " ")} investment horizon, and goal of ${preferences.goal.replace("_", " ")}, with monthly SIP of ₹${preferences.monthlyAmount}, give a 2-3 sentence recommendation summary for ${category} funds. Be concise and actionable.`;
      
      try {
        const chatResponse = await api.chat(insightQuery, null);
        if (chatResponse.response?.explanation) {
          // Extract first 2-3 sentences
          const sentences = chatResponse.response.explanation.split(/[.!?]+/).filter(s => s.trim()).slice(0, 3);
          setAiInsight(sentences.join(". ") + ".");
        }
      } catch (e) {
        // Fallback insight
        setAiInsight(`Based on your ${preferences.riskTolerance} risk profile and ${preferences.investmentHorizon.replace("_", " ")} horizon, ${category} funds are well-suited for your ${preferences.goal.replace("_", " ")} goal.`);
      }

      setStep("results");
    } catch (err) {
      console.error("Failed to get recommendations", err);
      setAiInsight("We found some funds that might interest you based on your preferences.");
      setStep("results");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNext = () => {
    const steps: Step[] = ["welcome", "goal", "risk", "horizon", "amount"];
    const currentIndex = steps.indexOf(step);
    if (currentIndex < steps.length - 1) {
      setStep(steps[currentIndex + 1]);
    } else {
      getRecommendations();
    }
  };

  const handleBack = () => {
    const steps: Step[] = ["welcome", "goal", "risk", "horizon", "amount"];
    const currentIndex = steps.indexOf(step);
    if (currentIndex > 0) {
      setStep(steps[currentIndex - 1]);
    }
  };

  const resetWizard = () => {
    setStep("welcome");
    setPreferences({
      goal: "",
      riskTolerance: "moderate",
      investmentHorizon: "medium_term",
      monthlyAmount: 5000,
    });
    setRecommendations([]);
    setAiInsight("");
  };

  const canProceed = () => {
    switch (step) {
      case "goal": return preferences.goal !== "";
      case "risk": return true;
      case "horizon": return true;
      case "amount": return preferences.monthlyAmount >= 500;
      default: return true;
    }
  };

  const getStepNumber = () => {
    const steps: Step[] = ["goal", "risk", "horizon", "amount"];
    return steps.indexOf(step) + 1;
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="w-full max-w-2xl bg-white dark:bg-zinc-900 rounded-3xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-violet-600 to-indigo-600 p-6 text-white relative overflow-hidden">
          <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4xIj48cGF0aCBkPSJNMzYgMzRjMC0yIDItNCAyLTRzLTItMi00LTItNC0yLTItNCAyLTQgMi00IDQtMiA0LTIgMi00IDItNHoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/20 transition-colors"
          >
            <X size={20} />
          </button>
          <div className="relative flex items-center gap-3">
            <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center">
              <Sparkles size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">AI Fund Finder</h2>
              <p className="text-white/80 text-sm">Personalized recommendations in 30 seconds</p>
            </div>
          </div>
          
          {/* Progress bar */}
          {step !== "welcome" && step !== "loading" && step !== "results" && (
            <div className="mt-4 flex gap-1">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full transition-colors ${
                    i <= getStepNumber() ? "bg-white" : "bg-white/30"
                  }`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-6">
          <AnimatePresence mode="wait">
            {/* Welcome Step */}
            {step === "welcome" && (
              <motion.div
                key="welcome"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="text-center py-8"
              >
                <div className="w-20 h-20 bg-gradient-to-br from-violet-100 to-indigo-100 dark:from-violet-900/30 dark:to-indigo-900/30 rounded-3xl flex items-center justify-center mx-auto mb-6">
                  <Sparkles size={40} className="text-violet-600 dark:text-violet-400" />
                </div>
                <h3 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-3">
                  Let AI Find Your Perfect Fund
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400 mb-8 max-w-md mx-auto">
                  Answer 4 quick questions and our AI will recommend the best mutual funds tailored to your goals and risk profile.
                </p>
                <button
                  onClick={handleNext}
                  className="inline-flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 text-white px-8 py-4 rounded-2xl font-bold hover:shadow-lg hover:shadow-violet-500/25 transition-all"
                >
                  Get Started
                  <ChevronRight size={20} />
                </button>
              </motion.div>
            )}

            {/* Goal Step */}
            {step === "goal" && (
              <motion.div
                key="goal"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                  What's your investment goal?
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                  Select the primary reason you want to invest
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {goals.map((goal) => (
                    <button
                      key={goal.id}
                      onClick={() => setPreferences({ ...preferences, goal: goal.id })}
                      className={`p-4 rounded-2xl border-2 transition-all text-left ${
                        preferences.goal === goal.id
                          ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
                          : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
                      }`}
                    >
                      <goal.icon
                        size={24}
                        className={preferences.goal === goal.id ? "text-violet-600" : "text-zinc-400"}
                      />
                      <div className="mt-2 font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                        {goal.label}
                      </div>
                      <div className="text-xs text-zinc-500">{goal.description}</div>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Risk Step */}
            {step === "risk" && (
              <motion.div
                key="risk"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                  What's your risk appetite?
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                  How much volatility can you handle?
                </p>
                <div className="space-y-3">
                  {riskOptions.map((option) => (
                    <button
                      key={option.id}
                      onClick={() => setPreferences({ ...preferences, riskTolerance: option.id as any })}
                      className={`w-full p-4 rounded-2xl border-2 transition-all flex items-center gap-4 ${
                        preferences.riskTolerance === option.id
                          ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
                          : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
                      }`}
                    >
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                        option.color === "emerald" ? "bg-emerald-100 dark:bg-emerald-900/30" :
                        option.color === "amber" ? "bg-amber-100 dark:bg-amber-900/30" :
                        "bg-rose-100 dark:bg-rose-900/30"
                      }`}>
                        <option.icon size={24} className={
                          option.color === "emerald" ? "text-emerald-600" :
                          option.color === "amber" ? "text-amber-600" :
                          "text-rose-600"
                        } />
                      </div>
                      <div className="text-left">
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100">{option.label}</div>
                        <div className="text-sm text-zinc-500">{option.description}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Horizon Step */}
            {step === "horizon" && (
              <motion.div
                key="horizon"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                  Investment timeline?
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                  How long do you plan to stay invested?
                </p>
                <div className="flex gap-3">
                  {horizonOptions.map((option) => (
                    <button
                      key={option.id}
                      onClick={() => setPreferences({ ...preferences, investmentHorizon: option.id as any })}
                      className={`flex-1 p-4 rounded-2xl border-2 transition-all text-center ${
                        preferences.investmentHorizon === option.id
                          ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
                          : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
                      }`}
                    >
                      <Clock size={24} className={`mx-auto mb-2 ${
                        preferences.investmentHorizon === option.id ? "text-violet-600" : "text-zinc-400"
                      }`} />
                      <div className="font-semibold text-zinc-900 dark:text-zinc-100">{option.label}</div>
                      <div className="text-xs text-zinc-500">{option.description}</div>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Amount Step */}
            {step === "amount" && (
              <motion.div
                key="amount"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                  Monthly SIP amount?
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                  How much can you invest monthly?
                </p>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <Wallet size={24} className="text-violet-600" />
                    <input
                      type="range"
                      min="500"
                      max="100000"
                      step="500"
                      value={preferences.monthlyAmount}
                      onChange={(e) => setPreferences({ ...preferences, monthlyAmount: parseInt(e.target.value) })}
                      className="flex-1 h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full appearance-none cursor-pointer accent-violet-600"
                    />
                  </div>
                  <div className="text-center">
                    <span className="text-4xl font-bold text-zinc-900 dark:text-zinc-100">
                      ₹{preferences.monthlyAmount.toLocaleString()}
                    </span>
                    <span className="text-zinc-500 ml-2">/month</span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-500">
                    <span>₹500</span>
                    <span>₹1,00,000</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Loading Step */}
            {step === "loading" && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center py-12"
              >
                <div className="w-16 h-16 bg-violet-100 dark:bg-violet-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Loader2 size={32} className="text-violet-600 animate-spin" />
                </div>
                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
                  Finding your perfect funds...
                </h3>
                <p className="text-zinc-500 dark:text-zinc-400">
                  Our AI is analyzing thousands of funds
                </p>
              </motion.div>
            )}

            {/* Results Step */}
            {step === "results" && (
              <motion.div
                key="results"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                {/* AI Insight */}
                {aiInsight && (
                  <div className="bg-gradient-to-r from-violet-50 to-indigo-50 dark:from-violet-900/20 dark:to-indigo-900/20 rounded-2xl p-4 mb-6 border border-violet-200 dark:border-violet-800">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Sparkles size={16} className="text-white" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-violet-600 dark:text-violet-400 uppercase tracking-wider mb-1">
                          AI Recommendation
                        </div>
                        <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
                          {aiInsight}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-4">
                  Recommended Funds ({recommendations.length})
                </h3>

                {recommendations.length > 0 ? (
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-2">
                    {recommendations.map((fund) => (
                      <button
                        key={fund.scheme_code}
                        onClick={() => onFundSelect(fund)}
                        className="w-full p-4 rounded-xl border border-zinc-200 dark:border-zinc-700 hover:border-violet-300 dark:hover:border-violet-700 hover:bg-violet-50 dark:hover:bg-violet-900/10 transition-all text-left group"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-zinc-900 dark:text-zinc-100 truncate text-sm">
                              {fund.scheme_name}
                            </div>
                            <div className="text-xs text-zinc-500 mt-1">
                              NAV: ₹{fund.nav?.toFixed(2) || "N/A"} • {fund.category || "Equity"}
                            </div>
                          </div>
                          <ChevronRight size={20} className="text-zinc-400 group-hover:text-violet-600 transition-colors flex-shrink-0" />
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-zinc-500">
                    No funds found. Try adjusting your preferences.
                  </div>
                )}

                <button
                  onClick={resetWizard}
                  className="mt-4 w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors text-sm font-medium"
                >
                  <RefreshCcw size={16} />
                  Start Over
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer Navigation */}
        {step !== "welcome" && step !== "loading" && step !== "results" && (
          <div className="px-6 pb-6 flex justify-between">
            <button
              onClick={handleBack}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <ChevronLeft size={20} />
              Back
            </button>
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className={`flex items-center gap-2 px-6 py-2 rounded-xl font-semibold transition-all ${
                canProceed()
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white hover:shadow-lg hover:shadow-violet-500/25"
                  : "bg-zinc-200 dark:bg-zinc-700 text-zinc-400 cursor-not-allowed"
              }`}
            >
              {step === "amount" ? "Get Recommendations" : "Next"}
              <ChevronRight size={20} />
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
};
