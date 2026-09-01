import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
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
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Pick a topic to ground research chat…"
          className="w-full pl-8 pr-3 py-2 text-xs sm:text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {open && matches.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
          {matches.map((t) => (
            <button
              type="button"
              key={t.topic_id}
              onClick={() => {
                onSelect(t.topic_id);
                setQ("");
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2.5 text-xs sm:text-sm hover:bg-indigo-50/70 border-b border-slate-50 last:border-0 transition"
            >
              <div className="text-slate-900 font-medium line-clamp-1">{t.title}</div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                {t.topic_id}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
