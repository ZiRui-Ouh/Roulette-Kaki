import { useState, useEffect } from "react";
import ChatInput from "../components/ChatInput";
import ChatMessage from "../components/ChatMessage";
import { askQuery } from "../api";
import { loadQueryMessages, saveQueryMessages, clearQueryMessages } from "../session";
import { useLanguage } from "../contexts/LanguageContext";
import type { ChatMessage as ChatMessageType } from "../types";
import {
  Sparkles,
  Trash2,
  HelpCircle,
  Building,
  HeartPulse,
  GraduationCap,
  Coins,
  ShieldAlert,
} from "lucide-react";

const SUGGESTED_TOPICS = [
  {
    icon: Building,
    title: "HDB BTO Singles Eligibility",
    query: "What are the eligibility criteria and income ceilings for singles applying for an HDB BTO flat in Singapore?",
  },
  {
    icon: Coins,
    title: "CPF Retirement Sum Schemes",
    query: "Explain the differences between the Basic, Full, and Enhanced Retirement Sums in CPF, and how CPF LIFE payouts work.",
  },
  {
    icon: HeartPulse,
    title: "MediShield Life Coverage Limits",
    query: "What are the claim limits, deductibles, and pre-existing condition coverages under MediShield Life?",
  },
  {
    icon: GraduationCap,
    title: "SkillsFuture Credit Claim Rules",
    query: "How can Singapore Citizens utilize their SkillsFuture Credits and the SkillsFuture Level-Up Programme top-ups?",
  },
];

export default function QueryPage() {
  // This page is the policy question workflow: restore local history, send a
  // question to the backend, then append the returned answer to the chat.
  const { language } = useLanguage();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Hydrate messages from the per-language localStorage bucket.
  // Re-runs when the user flips languages so each bucket shows its own
  // history (no cross-script mixing inside a single thread).
  useEffect(() => {
    setMessages(loadQueryMessages(language));
    setErrorBanner(null);
  }, [language]);

  // Save messages to the per-language bucket on update.
  useEffect(() => {
    if (messages.length > 0) {
      saveQueryMessages(messages, language);
    }
  }, [messages, language]);

  const handleClearHistory = () => {
    clearQueryMessages(language);
    setMessages([]);
    setSessionId(null);
    setErrorBanner(null);
  };

  const handleSend = async (question: string) => {
    // Show the user's message immediately, then replace the loading state with
    // either the agent's answer or a clear connection error.
    const userMsg: ChatMessageType = {
      role: "user",
      content: question,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setErrorBanner(null);

    try {
      const res = await askQuery(question, language, sessionId || undefined);

      if (res.session_id) {
        setSessionId(res.session_id);
      }

      const assistantMsg: ChatMessageType = {
        role: "assistant",
        content: res.answer,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      console.error("Failed to query backend:", err);
      const errMsg =
        err instanceof Error
          ? err.message
          : "Unable to reach the Query Agent backend. Please ensure the backend server is running on http://127.0.0.1:8000.";

      setErrorBanner(errMsg);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "⚠️ **Connection Error**: I could not retrieve an answer from the Policy Query Agent backend. Please check that the backend FastAPI server is running on `http://127.0.0.1:8000`.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-[calc(100vh-130px)]">
      {/* Top Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Singapore Government Policy Intelligence</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Policy Query Agent
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Ask questions about Singapore policies, subsidies, schemes, and regulations. Grounded strictly in official government sources.
          </p>
        </div>

        {messages.length > 0 && (
          <button
            onClick={handleClearHistory}
            disabled={isLoading}
            className="self-start md:self-center inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-medium text-slate-600 hover:text-slate-900 transition shadow-2xs disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Chat</span>
          </button>
        )}
      </div>

      {errorBanner && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs sm:text-sm text-amber-900 flex items-start gap-2 shadow-2xs">
          <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Backend Notice:</span> {errorBanner}
          </div>
        </div>
      )}

      {/* Main chat stream / Empty state */}
      <div className="flex-1 py-6">
        {messages.length === 0 ? (
          <div className="py-8 sm:py-12 max-w-2xl mx-auto text-center space-y-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-emerald-400 text-white flex items-center justify-center mx-auto shadow-md">
              <HelpCircle className="w-7 h-7" />
            </div>

            <div>
              <h2 className="text-xl font-bold text-slate-900">
                How can I assist you with Singapore policies today?
              </h2>
              <p className="mt-2 text-sm text-slate-500 max-w-lg mx-auto">
                Get clear, concise, and accurate explanations for CPF, HDB housing grants, healthcare subsidies, tax policies, and more.
              </p>
            </div>

            <div className="pt-2 text-left">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 text-center">
                Suggested Policy Questions
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {SUGGESTED_TOPICS.map((topic, i) => {
                  const Icon = topic.icon;
                  return (
                    <button
                      key={i}
                      onClick={() => handleSend(topic.query)}
                      disabled={isLoading}
                      className="group text-left p-3.5 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-sm transition flex flex-col justify-between"
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="w-6 h-6 rounded-md bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <span className="text-xs font-semibold text-slate-900">
                          {topic.title}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                        {topic.query}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m, index) => (
              <ChatMessage
                key={index}
                role={m.role}
                content={m.content}
                grounded={m.grounded}
              />
            ))}

            {isLoading && (
              <div className="flex items-center gap-3 my-4">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center shrink-0">
                  <Sparkles className="w-4 h-4 animate-spin" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3 text-xs sm:text-sm text-slate-500 flex items-center gap-2 shadow-2xs">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "0ms" }}></span>
                    <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </div>
                  <span>Policy Agent is researching official guidelines…</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input bar pinned at bottom */}
      <div className="sticky bottom-4 z-20 mt-auto pt-2 bg-gradient-to-t from-stone-50 via-stone-50/90 to-transparent">
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}