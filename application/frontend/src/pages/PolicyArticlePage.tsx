import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  ArrowLeft,
  Sparkles,
  Send,
  RefreshCw,
  Landmark,
  Calendar,
  ExternalLink,
  ShieldCheck,
  HelpCircle,
  RotateCcw,
  CheckCircle2,
  FileText,
  AlertCircle,
  Copy,
  Check,
} from "lucide-react";
import { POLICIES } from "../data/policies";
import { askQuery } from "../api";
import { useLanguage } from "../contexts/LanguageContext";
import VoiceInputButton from "../components/VoiceInputButton";
import type { ChatMessage } from "../types";

export default function PolicyArticlePage() {
  // This page reads the policy id from the URL and displays the matching
  // article from the local policy data set.
  const { id } = useParams<{ id: string }>();
  const policy = POLICIES.find((p) => p.id === id);
  const { language } = useLanguage();

  // Chat conversation state for this policy
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [inputVal, setInputVal] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Helper to construct a clean interactive concierge greeting for the chatbot
  const getInitialConciergeMessage = (title: string, ministry: string): ChatMessage => ({
    role: "assistant",
    content: `👋 **Welcome to the Policy Intelligence Concierge.**\n\nI have indexed the official government gazettes, circulars, and rules for **${title}** (${ministry}).\n\nAsk me any question below regarding your eligibility, income ceilings, grant calculations, resale restrictions, or MOP rules — or select a suggested inquiry below to get started!`,
    timestamp: Date.now(),
  });

  // Initialize chat messages with clean concierge greeting (briefing is rendered outside the chatbot)
  useEffect(() => {
    if (policy) {
      setMessages([getInitialConciergeMessage(policy.title, policy.ministry)]);
      setSessionId(null);
      setErrorMsg(null);
    }
  }, [policy?.id]);

  // Auto scroll down when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async (questionText?: string) => {
    const queryText = (questionText || inputVal).trim();
    if (!queryText || isLoading || !policy) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: queryText,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputVal("");
    setIsLoading(true);
    setErrorMsg(null);

    try {
      // Prime the question with policy context if appropriate
      const contextualQuestion = `Regarding the Singapore policy "${policy.title}" (${policy.ministry}): ${queryText}`;
      const res = await askQuery(contextualQuestion, language, sessionId || undefined);

      if (res.session_id) {
        setSessionId(res.session_id);
      }

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: res.answer,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      console.error("Query failed:", err);
      const errText =
        err instanceof Error
          ? err.message
          : "Unable to connect to Query Agent. Please ensure the backend server is running.";
      setErrorMsg(errText);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleResetChat = () => {
    if (policy) {
      setMessages([getInitialConciergeMessage(policy.title, policy.ministry)]);
      setErrorMsg(null);
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleTranscript = (transcriptText: string) => {
    setInputVal((prev) => (prev ? `${prev} ${transcriptText}` : transcriptText));
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  if (!policy) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <AlertCircle className="w-12 h-12 text-stone-400 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-stone-900">Policy Dispatch Not Found</h2>
        <p className="text-stone-500 text-sm mt-1 mb-6">
          The requested policy article could not be located in our gazette index.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Front Page</span>
        </Link>
      </div>
    );
  }

  const relatedPolicies = POLICIES.filter(
    (p) => p.id !== policy.id && (policy.relatedPolicyIds?.includes(p.id) || p.category === policy.category),
  ).slice(0, 3);

  // Clean trailing chat-prompt CTA from the executive briefing so it renders as a clean official dispatch
  const briefingMarkdown = (policy.initialBriefing || "")
    .replace(/---\s*💡\s*\*Ask me any question below[^\n]*\*/gi, "")
    .trim();

  return (
    <div className="pb-16 max-w-7xl mx-auto">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between gap-4 mb-6 pt-2 border-b border-stone-200/80 pb-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-500 hover:text-stone-900 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Front Page</span>
          <span className="text-stone-300">/</span>
          <span className="text-stone-400">{policy.category}</span>
        </Link>

        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={handleCopyLink}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-stone-100 text-stone-600 hover:text-stone-900 hover:bg-stone-200/70 transition"
          >
            {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedLink ? "Link Copied" : "Share Policy"}</span>
          </button>
        </div>
      </div>

      {/* Article Header */}
      <div className="max-w-4xl mb-8">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="bg-stone-900 text-white text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded">
            {policy.category} Desk
          </span>
          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-600" />
            Official Policy Directive
          </span>
          <span className="text-stone-400 text-xs">&bull;</span>
          <span className="text-stone-500 text-xs flex items-center gap-1">
            <Calendar className="w-3 h-3 text-stone-400" />
            Effective: {policy.effectiveDate}
          </span>
        </div>

        <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl font-black text-stone-900 leading-[1.15] tracking-tight">
          {policy.headline}
        </h1>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-stone-500 pt-3 border-t border-stone-200">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-stone-700 flex items-center gap-1">
              <Landmark className="w-3.5 h-3.5 text-stone-500" />
              {policy.ministry}
            </span>
            <span>&bull;</span>
            <span>{policy.publishedAt}</span>
          </div>

          <div className="inline-flex items-center gap-1.5 text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-md font-medium text-[11px]">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Interactive AI Chat Mode Active</span>
          </div>
        </div>
      </div>

      {/* Main Content Layout: Executive Policy Digest + Interactive Concierge + Editorial Sidebar */}
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left Column: 1. Executive Briefing Card (outside chatbot), 2. Query Agent Chatbot */}
        <div className="space-y-6">
          {/* ============================================================== */}
          {/* 1. EXECUTIVE POLICY BRIEFING (ORGANIZED OUTSIDE CHATBOT)       */}
          {/* ============================================================== */}
          <article className="bg-white border border-stone-200/90 rounded-2xl shadow-xs overflow-hidden">
            {/* Top Bar Header */}
            <div className="bg-stone-900 text-white px-5 py-3.5 flex items-center justify-between gap-3 border-b border-stone-800">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white shadow-xs">
                  <FileText className="w-4 h-4 text-emerald-100" />
                </div>
                <div>
                  <div className="font-bold text-xs sm:text-sm text-white flex items-center gap-1.5">
                    <span>Executive Policy Briefing &amp; Digest</span>
                    <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] uppercase px-1.5 py-0.2 rounded font-mono">
                      Official Gazette
                    </span>
                  </div>
                  <div className="text-[11px] text-stone-400">
                    Structured regulatory summary &bull; Grounded in government circulars
                  </div>
                </div>
              </div>

              <div className="hidden sm:flex items-center gap-1.5 text-[11px] text-stone-300 bg-stone-800/80 px-2.5 py-1 rounded-md border border-stone-700">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Verified Directives</span>
              </div>
            </div>

            {/* Briefing Card Content */}
            <div className="p-5 sm:p-7">
              {policy.leadParagraph && (
                <div className="mb-6 pb-5 border-b border-stone-200/70 bg-stone-50/60 -mx-5 -mt-5 sm:-mx-7 sm:-mt-7 p-5 sm:p-7 border-t-0">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1.5 flex items-center gap-1.5">
                    <Landmark className="w-3.5 h-3.5 text-stone-400" />
                    <span>Official Gazette Abstract</span>
                  </div>
                  <p className="text-sm sm:text-base text-stone-800 font-serif leading-relaxed italic">
                    &ldquo;{policy.leadParagraph}&rdquo;
                  </p>
                </div>
              )}

              {/* Formatted Markdown Briefing */}
              <div className="prose-chat text-xs sm:text-sm leading-relaxed text-stone-800 space-y-3">
                <ReactMarkdown>{briefingMarkdown}</ReactMarkdown>
              </div>

              {/* Briefing Card Footer */}
              <div className="mt-6 pt-4 border-t border-stone-100 flex flex-wrap items-center justify-between gap-3 text-[11px] text-stone-500">
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1 text-emerald-700 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Official Singapore Government Gazette Grounding
                  </span>
                  <span className="text-stone-300 hidden sm:inline">&bull;</span>
                  <span className="hidden sm:inline text-stone-500">{policy.ministry}</span>
                </div>
                <div className="flex items-center gap-1.5 text-indigo-700 font-medium bg-indigo-50 px-2.5 py-1 rounded-md">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Interactive Q&amp;A Agent Below</span>
                </div>
              </div>
            </div>
          </article>

          {/* ============================================================== */}
          {/* 2. INTERACTIVE POLICY QUERY AGENT (CHATBOT)                    */}
          {/* ============================================================== */}
          <div className="flex flex-col bg-white border border-stone-200/90 rounded-2xl shadow-xs overflow-hidden">
            {/* Chat Bubble Top Bar */}
            <div className="bg-stone-900 text-white px-5 py-3.5 flex items-center justify-between gap-3 border-b border-stone-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
                <Sparkles className="w-4 h-4 text-amber-300" />
              </div>
              <div>
                <div className="font-bold text-xs sm:text-sm text-white flex items-center gap-1.5">
                  <span>Policy Query Agent</span>
                  <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] uppercase px-1.5 py-0.2 rounded font-mono">
                    Live Verified
                  </span>
                </div>
                <div className="text-[11px] text-stone-400">
                  Grounding answers in official government gazettes &amp; rules
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleResetChat}
              title="Reset conversation"
              className="text-stone-400 hover:text-white p-1.5 rounded-lg hover:bg-stone-800 transition cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>

          {/* Chat Stream Area */}
          <div className="p-4 sm:p-6 space-y-6 flex-1 min-h-[300px] max-h-[580px] overflow-y-auto bg-stone-50/50">
            {messages.map((msg, idx) => {
              const isAssistant = msg.role === "assistant";
              return (
                <div
                  key={idx}
                  className={`flex gap-3 ${
                    isAssistant ? "justify-start" : "justify-end"
                  }`}
                >
                  {isAssistant && (
                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs mt-1">
                      <Sparkles className="w-4 h-4 text-amber-300" />
                    </div>
                  )}

                  <div
                    className={`max-w-[88%] sm:max-w-[82%] rounded-2xl px-4 sm:px-5 py-3.5 shadow-xs ${
                      isAssistant
                        ? "bg-white border border-stone-200/90 text-stone-800"
                        : "bg-indigo-600 text-white"
                    }`}
                  >
                    <div
                      className={`text-xs sm:text-sm leading-relaxed ${
                        isAssistant ? "prose-chat" : "whitespace-pre-wrap font-sans"
                      }`}
                    >
                      {isAssistant ? (
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      ) : (
                        msg.content
                      )}
                    </div>

                    {isAssistant && (
                      <div className="mt-3 pt-2 border-t border-stone-100 flex items-center justify-between text-[10px] text-stone-400">
                        <span className="flex items-center gap-1 text-emerald-600 font-medium">
                          <CheckCircle2 className="w-3 h-3" />
                          Official SG Policy Verification
                        </span>
                        <span>Amazon Nova Intelligence</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                  <RefreshCw className="w-4 h-4 animate-spin text-amber-300" />
                </div>
                <div className="bg-white border border-stone-200/90 rounded-2xl px-5 py-4 shadow-xs text-xs text-stone-500 flex items-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                  <span>Searching official government databases &amp; synthesizing answer…</span>
                </div>
              </div>
            )}

            {/* Error Message */}
            {errorMsg && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">Query Encountered An Issue</div>
                  <div>{errorMsg}</div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Contextual Suggested Prompt Chips */}
          <div className="p-3.5 bg-white border-t border-stone-200">
            <div className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mb-2 flex items-center gap-1">
              <HelpCircle className="w-3 h-3 text-indigo-500" />
              Suggested Inquiries For This Policy:
            </div>
            <div className="flex flex-wrap gap-1.5">
              {policy.suggestedQuestions.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(q)}
                  disabled={isLoading}
                  className="text-xs bg-stone-100 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 text-stone-700 px-3 py-1.5 rounded-lg border border-stone-200/80 transition text-left cursor-pointer disabled:opacity-50"
                >
                  &ldquo;{q}&rdquo;
                </button>
              ))}
            </div>
          </div>

          {/* Chat Input Bar */}
          <div className="p-3.5 bg-stone-50 border-t border-stone-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <textarea
                ref={textareaRef}
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask any question regarding ${policy.title} (e.g. eligibility, figures)...`}
                rows={1}
                disabled={isLoading}
                className="flex-1 resize-none py-2.5 px-3.5 rounded-xl border border-stone-300 bg-white text-xs sm:text-sm text-stone-900 placeholder-stone-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-50"
              />

              <VoiceInputButton
                onTranscript={handleTranscript}
                disabled={isLoading}
              />

              <button
                type="submit"
                disabled={!inputVal.trim() || isLoading}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-stone-300 text-white px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition flex items-center gap-1.5 cursor-pointer disabled:cursor-not-allowed shadow-xs shrink-0"
              >
                {isLoading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Ask AI</span>
                    <Send className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>
            <div className="text-[10px] text-stone-400 mt-2 text-center">
              Press <kbd className="px-1 py-0.5 bg-stone-200 text-stone-700 rounded font-mono">Enter</kbd> to submit query &bull; Shift + Enter for newline
            </div>
          </div>
        </div>
      </div>

        {/* ============================================================== */}
        {/* EDITORIAL NEWS SIDEBAR                                          */}
        {/* ============================================================== */}
        <aside className="space-y-6">
          {/* Key Facts Sheet */}
          <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-stone-100">
              <h3 className="font-serif font-bold text-sm text-stone-900 uppercase tracking-wider">
                Policy Fact Sheet
              </h3>
              <span className="text-[10px] text-stone-400">At A Glance</span>
            </div>

            <div className="space-y-3">
              {policy.keyFacts.map((fact, idx) => (
                <div key={idx} className="bg-stone-50/80 p-2.5 rounded-xl border border-stone-200/60">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-stone-500">
                    {fact.label}
                  </div>
                  <div className="text-xs font-bold text-stone-900 mt-0.5">
                    {fact.value}
                  </div>
                  {fact.note && (
                    <div className="text-[10px] text-stone-500 mt-0.5">
                      {fact.note}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Official Gazette Documents */}
          <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-900 pb-3 mb-3 border-b border-stone-100">
              <FileText className="w-4 h-4 text-indigo-600" />
              <span>Official Circulars &amp; Sources</span>
            </div>

            <div className="space-y-2.5">
              {policy.officialSources.map((source, idx) => (
                <a
                  key={idx}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group block p-3 rounded-xl bg-stone-50 hover:bg-stone-100 border border-stone-200/70 transition"
                >
                  <div className="text-xs font-semibold text-stone-800 group-hover:text-indigo-600 transition flex items-start justify-between gap-2">
                    <span>{source.title}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-stone-400 group-hover:text-indigo-600 shrink-0 mt-0.5" />
                  </div>
                  <div className="text-[10px] text-stone-500 mt-1">
                    Source: {source.authority}
                  </div>
                </a>
              ))}
            </div>
          </div>

          {/* Related Policy Dispatches */}
          {relatedPolicies.length > 0 && (
            <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs">
              <div className="text-xs font-bold uppercase tracking-wider text-stone-900 pb-3 mb-3 border-b border-stone-100">
                Related Policy Dispatches
              </div>

              <div className="space-y-3">
                {relatedPolicies.map((rp) => (
                  <Link
                    key={rp.id}
                    to={`/policy/${rp.id}`}
                    className="block group p-2.5 rounded-xl hover:bg-stone-50 border border-transparent hover:border-stone-200 transition"
                  >
                    <div className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider">
                      {rp.category}
                    </div>
                    <div className="text-xs font-semibold text-stone-800 group-hover:text-indigo-600 transition line-clamp-2 mt-0.5">
                      {rp.headline}
                    </div>
                    <div className="text-[10px] text-stone-400 mt-1">
                      {rp.publishedAt}
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
