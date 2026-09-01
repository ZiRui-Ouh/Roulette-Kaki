import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChat } from "../api";
import { loadSession, saveSession } from "../session";
import type { ChatMessage, Digest } from "../types";
import TopicSelector from "./TopicSelector";

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
    const s = loadSession(digest.date);
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
      saveSession(digest.date, {
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
    <section className="rounded-lg border border-slate-200 bg-white flex flex-col h-[70vh]">
      <div className="border-b border-slate-200 p-3">
        <h2 className="font-semibold text-slate-900 text-sm">Chat</h2>
        {topicIds.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {topicIds.map((tid) => (
              <span
                key={tid}
                className="text-xs bg-slate-100 text-slate-700 rounded-full px-2 py-0.5"
                title={tid}
              >
                {truncate(topicById.get(tid)?.title ?? tid, 40)}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-slate-500 italic">
            Pick a topic below, then ask a question.
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
        {busy && (
          <div className="text-sm text-slate-500 italic">Thinking…</div>
        )}
        {banner && (
          <div className="text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded-md p-2">
            {banner}
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 p-3 space-y-2">
        <TopicSelector
          topics={digest.topics}
          onSelect={(tid) => setPendingTopic(tid)}
        />
        {pendingTopic && (
          <div className="text-xs text-slate-600 flex items-center gap-2">
            <span>
              Next message loads:{" "}
              <span className="font-medium">
                {truncate(
                  topicById.get(pendingTopic)?.title ?? pendingTopic,
                  50,
                )}
              </span>
            </span>
            <button
              onClick={() => setPendingTopic(null)}
              className="text-slate-400 hover:text-slate-700"
              title="Cancel"
              aria-label="Cancel selected topic"
            >
              ✕
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
            placeholder="Ask a question about the loaded topic(s)…"
            rows={2}
            className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-slate-400"
            disabled={busy}
          />
          <button
            onClick={submit}
            disabled={busy || !input.trim()}
            className="rounded-md bg-slate-900 text-white text-sm px-3 py-2 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </section>
  );
}

function MessageBubble({ m }: { m: ChatMessage }) {
  const isUser = m.role === "user";
  return (
    <div className={isUser ? "text-right" : ""}>
      <div
        className={
          isUser
            ? "inline-block max-w-[85%] rounded-lg bg-slate-900 text-white text-sm px-3 py-2 text-left"
            : "inline-block max-w-[95%] rounded-lg bg-slate-50 text-slate-900 text-sm px-3 py-2 border border-slate-200 text-left"
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{m.content}</p>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown>{m.content}</ReactMarkdown>
          </div>
        )}
      </div>
      {!isUser && m.grounded === false && (
        <div className="mt-1 text-xs text-amber-700">
          ⚠ The report doesn&apos;t cover this
        </div>
      )}
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
