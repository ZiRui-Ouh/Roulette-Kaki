import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChat } from "../api";
import { loadDebateSession, saveDebateSession } from "../session";
import { useLanguage } from "../contexts/LanguageContext";
import type { ChatMessage, Digest } from "../types";
import TopicSelector from "./TopicSelector";
import { Sparkles, Bot, AlertCircle, X, Send, ShieldCheck, HelpCircle, Layers } from "lucide-react";

interface Props {
  digest: Digest;
  onSaveReplyAsFlashcards?: (replyText: string, topicIdsUsed: string[]) => void;
}

export default function ChatPanel({ digest, onSaveReplyAsFlashcards }: Props) {
  const { language } = useLanguage();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingTopic, setPendingTopic] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  // Hydrate from the per-language localStorage bucket. Re-runs on
  // language change so mixed-script threads never appear in one bucket.
  useEffect(() => {
    const s = loadDebateSession(digest.date, language);
    if (s) {
      setSessionId(s.session_id);
      setTopicIds(s.topic_ids);
      setMessages(s.messages);
    } else {
      setSessionId(null);
      setTopicIds([]);
      setMessages([]);
    }
    setPendingTopic(null);
    setBanner(null);
    setInput("");
  }, [digest.date, language]);

  // Persist on every change (per-language bucket).
  useEffect(() => {
    if (sessionId) {
      saveDebateSession(
        digest.date,
        {
          session_id: sessionId,
          topic_ids: topicIds,
          messages,
        },
        language,
      );
    }
  }, [digest.date, sessionId, topicIds, messages, language]);

  const topicById = new Map(digest.topics.map((t) => [t.topic_id, t]));

  async function handleSend(customText?: string) {
    const text = (customText || input).trim();
    if (!text || busy) return;
    // Only forward a topic_id when the user has explicitly picked one via
    // TopicSelector. Sending digest.topics[0] as a default caused two bugs:
    // (a) the model got a pre-attached topic unrelated to the question,
    // and (b) the "topic dropped" banner fired on every turn where the
    // model chose not to use that arbitrary default.
    const nextTopicId = pendingTopic ?? undefined;
    setBusy(true);
    setBanner(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    if (!customText) setInput("");

    try {
      const resp = await sendChat(digest.date, {
        session_id: sessionId ?? undefined,
        message: text,
        topic_id: nextTopicId,
        language,
      });
      setSessionId(resp.session_id);
      const prevTopicIds = topicIds;
      setTopicIds(resp.topics_used);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.reply,
          grounded: resp.grounded,
        },
      ]);
      // Only warn when the user explicitly picked a topic AND it didn't
      // survive the round-trip — that's the real "eviction" case.
      if (nextTopicId && !resp.topics_used.includes(nextTopicId)) {
        const wasCap = prevTopicIds.length >= 5;
        setBanner(
          wasCap
            ? "5-topic limit reached; the oldest topic was dropped."
            : `The topic "${topicById.get(nextTopicId)?.title ?? nextTopicId}" wasn't used in this answer.`
        );
      }
      setPendingTopic(null);
    } catch (e: unknown) {
      const err = e as { status?: number; error?: string; message?: string };
      const msg =
        err?.error === "no_digest_for_date"
          ? "Load the digest first, then try chatting."
          : err?.error === "scraper_not_available"
            ? "Backend is in fixture mode. Set SCRAPER_MODE=sprs to fetch real transcripts."
            : err?.message || "Something went wrong.";
      setBanner(msg);
      // Remove optimistic user message on failure
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  const suggestedQuestions = [
    "What key ministerial statements were delivered in this sitting?",
    "Summarize what MPs debated on public transport and cost of living.",
    "Which bills or legislative amendments were passed?",
  ];

  return (
    <section className="rounded-2xl border border-stone-200 bg-white flex flex-col h-[78vh] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-stone-200 p-4 bg-stone-50/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-stone-900 text-white flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            </div>
            <div>
              <h2 className="font-serif font-bold text-stone-900 text-sm">
                Hansard Research Agent
              </h2>
              <div className="text-[10px] text-stone-500 font-sans flex items-center gap-1">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                <span>Document-grounded AI</span>
              </div>
            </div>
          </div>
          <span className="text-[10px] font-mono font-medium text-stone-500 bg-white px-2 py-0.5 rounded border border-stone-200">
            Nova Pro
          </span>
        </div>

        {topicIds.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <span className="text-[10px] font-bold text-stone-500 uppercase tracking-wider self-center">
              Loaded Docs:
            </span>
            {topicIds.map((tid) => (
              <span
                key={tid}
                className="text-[11px] bg-stone-100 border border-stone-200 text-stone-800 font-medium rounded-md px-2 py-0.5"
                title={tid}
              >
                {truncate(topicById.get(tid)?.title ?? tid, 32)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Message history */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="py-6 px-2 text-center space-y-4">
            <div className="w-10 h-10 rounded-full bg-stone-100 text-stone-600 flex items-center justify-center mx-auto">
              <Bot className="w-5 h-5 text-stone-700" />
            </div>
            <div>
              <p className="font-serif font-bold text-sm text-stone-900">
                Inquire on this Parliament Sitting
              </p>
              <p className="text-xs text-stone-500 mt-1 max-w-xs mx-auto leading-relaxed">
                Ask specific questions regarding MP speeches, ministerial answers, or legislative motions debated during this session.
              </p>
            </div>

            {/* Suggested Question Pills */}
            <div className="space-y-1.5 pt-2 text-left">
              <div className="flex items-center gap-1 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
                <HelpCircle className="w-3 h-3" />
                Suggested Questions:
              </div>
              {suggestedQuestions.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(q)}
                  disabled={busy}
                  className="w-full text-left p-2 rounded-xl bg-stone-50 hover:bg-stone-100 text-stone-800 text-xs transition border border-stone-200/80 cursor-pointer"
                >
                  &ldquo;{q}&rdquo;
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            m={m}
            onSaveAsFlashcards={
              onSaveReplyAsFlashcards
                ? () => onSaveReplyAsFlashcards(m.content, topicIds)
                : undefined
            }
          />
        ))}

        {busy && (
          <div className="flex items-center gap-2 text-xs text-stone-500 italic p-2 bg-stone-50 rounded-xl border border-stone-100">
            <div className="w-2 h-2 rounded-full bg-stone-600 animate-pulse" />
            <span>Analyzing parliamentary Hansard debate documents…</span>
          </div>
        )}

        {banner && (
          <div className="text-xs bg-amber-50 border border-amber-200 text-amber-900 rounded-xl p-3 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span>{banner}</span>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-stone-200 p-3 space-y-2 bg-stone-50/50">
        <TopicSelector
          topics={digest.topics}
          onSelect={(tid) => setPendingTopic(tid)}
        />
        
        {pendingTopic && (
          <div className="text-xs text-stone-700 bg-stone-100 border border-stone-200 rounded-lg px-2.5 py-1.5 flex items-center justify-between gap-2">
            <span className="truncate text-[11px]">
              Active context:{" "}
              <span className="font-semibold text-stone-900">
                {truncate(
                  topicById.get(pendingTopic)?.title ?? pendingTopic,
                  40,
                )}
              </span>
            </span>
            <button
              onClick={() => setPendingTopic(null)}
              className="text-stone-400 hover:text-stone-700 p-0.5 cursor-pointer"
              title="Cancel"
              aria-label="Cancel selected topic"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything about this sitting…"
            rows={2}
            className="flex-1 border border-stone-300 rounded-xl px-3 py-2 text-xs resize-none focus:outline-hidden focus:ring-1 focus:ring-stone-800 bg-white text-stone-900"
            disabled={busy}
          />
          <button
            onClick={() => handleSend()}
            disabled={busy || !input.trim()}
            className="rounded-xl bg-stone-900 text-white text-xs px-3.5 py-2 font-semibold disabled:opacity-40 hover:bg-stone-800 transition flex items-center justify-center shrink-0 shadow-xs cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
}

function MessageBubble({
  m,
  onSaveAsFlashcards,
}: {
  m: ChatMessage;
  onSaveAsFlashcards?: () => void;
}) {
  const isUser = m.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[90%] rounded-2xl bg-stone-900 text-white text-xs px-4 py-2.5 text-left shadow-xs"
            : "max-w-[95%] rounded-2xl bg-white text-stone-900 text-xs px-4 py-3 border border-stone-200 text-left shadow-xs"
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
        ) : (
          <div className="prose prose-xs max-w-none prose-stone prose-p:leading-relaxed prose-headings:font-serif">
            <ReactMarkdown>{m.content}</ReactMarkdown>
          </div>
        )}
      </div>
      {!isUser && m.grounded === false && (
        <div className="mt-1 text-[10px] text-amber-700 flex items-center gap-1 font-medium px-1">
          <span>⚠️ The parliamentary report does not cover this inquiry.</span>
        </div>
      )}
      {!isUser && onSaveAsFlashcards && m.content.trim().length > 0 && (
        <button
          type="button"
          onClick={onSaveAsFlashcards}
          className="mt-1 inline-flex items-center gap-1 text-[10px] font-medium text-stone-500 hover:text-indigo-600 px-1 cursor-pointer transition"
          title="Condense this reply into flashcards"
        >
          <Layers className="w-3 h-3" />
          Save as flashcards
        </button>
      )}
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
