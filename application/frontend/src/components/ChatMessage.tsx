import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Check, Copy, Sparkles, User, ShieldCheck } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../types";

export default function ChatMessage({
  role,
  content,
  grounded,
}: ChatMessageType) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex w-full gap-3 my-4 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-indigo-600/10 border border-indigo-200 text-indigo-700 flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
          <Sparkles className="w-4 h-4" />
        </div>
      )}

      <div
        className={`relative group max-w-[90%] sm:max-w-[80%] rounded-2xl px-5 py-4 transition-all ${
          isUser
            ? "bg-slate-900 text-white shadow-sm"
            : "bg-white text-slate-900 border border-slate-200/90 shadow-sm"
        }`}
      >
        {!isUser && (
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 text-xs font-medium text-slate-500">
            <div className="flex items-center gap-1.5 text-indigo-700">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Policy Assistant (Amazon Nova)</span>
            </div>

            <button
              onClick={handleCopy}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100"
              title="Copy answer"
              aria-label="Copy message"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        )}

        {isUser ? (
          <p className="whitespace-pre-wrap text-sm sm:text-base leading-relaxed break-words">
            {content}
          </p>
        ) : (
          <div className="prose-chat text-sm sm:text-base break-words text-slate-800">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}

        {!isUser && grounded === false && (
          <div className="mt-3 pt-2 border-t border-amber-100 flex items-center gap-1.5 text-xs text-amber-800 font-medium">
            <span>⚠️ Official sources provided do not cover all details of this inquiry.</span>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
}