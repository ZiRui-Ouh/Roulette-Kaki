import { useEffect, useRef, useState } from "react";
import type { Topic } from "../types";

interface Props {
  topics: Topic[];
  onSelect: (topicId: string) => void;
}

export default function TopicSelector({ topics, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const query = q.trim().toLowerCase();
  const matches = query
    ? topics.filter((t) => t.title.toLowerCase().includes(query)).slice(0, 12)
    : topics.slice(0, 12);

  return (
    <div className="relative" ref={ref}>
      <input
        type="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Pick a topic to load into chat…"
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
      />
      {open && matches.length > 0 && (
        <div className="absolute z-10 mt-1 w-full max-h-64 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {matches.map((t) => (
            <button
              type="button"
              key={t.topic_id}
              onClick={() => {
                onSelect(t.topic_id);
                setQ("");
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-slate-100"
            >
              <div className="text-slate-900">{t.title}</div>
              <div className="text-xs text-slate-500 font-mono">
                {t.topic_id}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
