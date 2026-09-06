import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { SendHorizontal, Loader2 } from "lucide-react";
import VoiceInputButton from "./VoiceInputButton";

interface ChatInputProps {
  onSend: (question: string) => void;
  isLoading: boolean;
  placeholder?: string;
}

// Collects a message from the user and sends it to the parent chat workflow.
export default function ChatInput({
  onSend,
  isLoading,
  placeholder = "Ask a question about Singapore policies (e.g., CPF, BTO eligibility, SkillsFuture)...",
}: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140,
      )}px`;
    }
  };

  const handleTranscript = (transcriptText: string) => {
    setText((prev) => (prev ? `${prev} ${transcriptText}` : transcriptText));
    setTimeout(() => {
      handleInput();
      textareaRef.current?.focus();
    }, 50);
  };

  return (
    <div className="relative rounded-2xl border border-slate-300/80 bg-white p-2 shadow-md transition focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            handleInput();
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full max-h-36 resize-none bg-transparent px-3 py-2 text-sm sm:text-base text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:opacity-50"
        />

        <VoiceInputButton
          onTranscript={handleTranscript}
          disabled={isLoading}
        />

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !text.trim()}
          className="inline-flex items-center justify-center shrink-0 w-10 h-10 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 transition shadow-xs"
          title="Send query"
          aria-label="Send query"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <SendHorizontal className="w-5 h-5" />
          )}
        </button>
      </div>

      <div className="mt-1 flex items-center justify-between px-2 text-[11px] text-slate-400">
        <span>Press <kbd className="font-mono bg-slate-100 px-1 py-0.5 rounded text-[10px] text-slate-500">Enter</kbd> to send, <kbd className="font-mono bg-slate-100 px-1 py-0.5 rounded text-[10px] text-slate-500">Shift+Enter</kbd> for new line</span>
        <span className="hidden sm:inline">Answers grounded in official government sources</span>
      </div>
    </div>
  );
}
