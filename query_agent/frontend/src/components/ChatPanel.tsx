import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChat } from "../api";
import { loadDebateSession, saveDebateSession } from "../session";
import type { ChatMessage, Digest } from "../types";
import TopicSelector from "./TopicSelector";
import { Sparkles, Bot, AlertCircle, X, Send } from "lucide-react";

interface Props {
  digest: Digest;
}

export default function ChatPanel({ digest }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingTopic, setPendingTopic] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  // Hydrate from localStorage on mount / date change.
  useEffect(() => {
    const s = loadDebateSession(digest.date);
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
  }, [digest.date]);

  // Persist on every change.
  useEffect(() => {
    if (sessionId) {
      saveDebateSession(digest.date, {
        session_id: sessionId,
        topic_ids: topicIds,
        messages,
      });
    }
  }, [digest.date, sessionId, topicIds, messages]);

  const topicById = new Map(digest.topics.map((t) => [t.topic_id, t]));

  async function submit() {
    const text = input.trim();
    if (!text || busy) return;
    const nextTopicId = pendingTopic ?? undefined;
    setBusy(true);
    setBanner(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    try {
      const resp = await sendChat(digest.date, {
        session_id: sessionId ?? undefined,
        message: text,
        topic_id: nextTopicId,
      });
      setSessionId(resp.session_id);
      setTopicIds(resp.topics_used);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.reply,
          grounded: resp.grounded,
        },
      ]);
      if (nextTopicId && !resp.topics_used.includes(nextTopicId)) {
        setBanner("5-topic limit reached; the oldest topic was dropped.");
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
      // Remove the optimistic user message so a retry doesn't duplicate.
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white flex flex-col h-[75vh] shadow-sm">
      <div className="border-b border-slate-200/80 p-3.5 bg-slate-50/50 rounded-t-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <h2 className="font-semibold text-slate-900 text-sm">
              Debate Research Assistant
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">Nova Pro</span>
        </div>

        {topicIds.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <span className="text-[11px] text-slate-500 self-center">Loaded:</span>
            {topicIds.map((tid) => (
              <span
                key={tid}
                className="text-[11px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-medium rounded-md px-2 py-0.5"
                title={tid}
              >
                {truncate(topicById.get(tid)?.title ?? tid, 35)}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
        {messages.length === 0 && (
          <div className="text-center py-8 px-4 text-sm text-slate-500 space-y-2">
            <Bot className="w-8 h-8 text-slate-300 mx-auto" />
            <p className="font-medium text-slate-700">Ask about this sitting</p>
            <p className="text-xs text-slate-400">
              Pick a topic from below to load its full parliamentary report into context, then ask any specific question.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-slate-500 italic p-2">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span>Analyzing debate documents…</span>
          </div>
        )}
        {banner && (
          <div className="text-xs bg-amber-50 border border-amber-200 text-amber-900 rounded-lg p-2.5 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span>{banner}</span>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 p-3 space-y-2.5 bg-slate-50/40 rounded-b-xl">
        <TopicSelector
          topics={digest.topics}
          onSelect={(tid) => setPendingTopic(tid)}
        />
        {pendingTopic && (
          <div className="text-xs text-slate-700 bg-indigo-50/80 border border-indigo-100 rounded-lg px-2.5 py-1.5 flex items-center justify-between gap-2">
            <span className="truncate">
              Next query loads:{" "}
              <span className="font-semibold text-indigo-900">
                {truncate(
                  topicById.get(pendingTopic)?.title ?? pendingTopic,
                  45,
                )}
              </span>
            </span>
            <button
              onClick={() => setPendingTopic(null)}
              className="text-slate-400 hover:text-slate-700 p-0.5"
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
                submit();
              }
            }}
            placeholder="Ask a question about the sitting…"
            rows={2}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-xs sm:text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            disabled={busy}
          />
          <button
            onClick={submit}
            disabled={busy || !input.trim()}
            className="rounded-lg bg-slate-900 text-white text-xs sm:text-sm px-3.5 py-2 font-medium disabled:opacity-40 hover:bg-slate-800 transition flex items-center justify-center shrink-0 shadow-xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
}

function MessageBubble({ m }: { m: ChatMessage }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[90%] rounded-xl bg-slate-900 text-white text-xs sm:text-sm px-3.5 py-2.5 text-left shadow-xs"
            : "max-w-[95%] rounded-xl bg-white text-slate-900 text-xs sm:text-sm px-3.5 py-2.5 border border-slate-200 text-left shadow-xs"
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{m.content}</p>
        ) : (
          <div className="prose-chat text-xs sm:text-sm">
            <ReactMarkdown>{m.content}</ReactMarkdown>
          </div>
        )}
      </div>
      {!isUser && m.grounded === false && (
        <div className="mt-1 text-[11px] text-amber-700 flex items-center gap-1 font-medium">
          <span>⚠️ The parliamentary report does not cover this inquiry.</span>
        </div>
      )}
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
