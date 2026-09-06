import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X, Users } from "lucide-react";
import type { Topic } from "../types";
import { highlightMatches, tokenize, matchesAllTokens } from "../lib/textMatch";

interface Props {
  topics: Topic[];
  onSelect: (topicId: string) => void;
}

const MAX_RESULTS = 12;

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

  const tokens = useMemo(() => tokenize(q), [q]);

  // Dedup by topic_id (backend occasionally returns duplicates). Same
  // duplicate-key issue as in TopicList — dedup here too so the dropdown
  // never repeats an entry.
  const uniqueTopics = useMemo(() => {
    const seen = new Set<string>();
    return topics.filter((t) => {
      if (!t.topic_id || seen.has(t.topic_id)) return false;
      seen.add(t.topic_id);
      return true;
    });
  }, [topics]);

  const { matches, totalMatches } = useMemo(() => {
    const all = tokens.length
      ? uniqueTopics.filter((t) =>
          matchesAllTokens(tokens, [t.title, ...(t.speakers ?? [])]),
        )
      : uniqueTopics;
    return {
      matches: all.slice(0, MAX_RESULTS),
      totalMatches: all.length,
    };
  }, [uniqueTopics, tokens]);

  const hasMore = totalMatches > matches.length;

  return (
    <div className="relative" ref={ref}>
      <div className="relative">
        <Search className="w-4 h-4 text-indigo-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Pick a topic to ground research chat…"
          className="w-full pl-9 pr-9 py-2.5 text-sm border-2 border-indigo-200 rounded-lg bg-white text-stone-900 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm transition"
        />
        {q && (
          <button
            type="button"
            onClick={() => {
              setQ("");
              setOpen(true);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 p-1 cursor-pointer"
            title="Clear"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute z-20 bottom-full mb-1.5 w-full max-h-72 overflow-y-auto rounded-xl border border-stone-300 bg-white shadow-2xl ring-1 ring-black/5">
          {matches.length === 0 ? (
            <div className="px-3 py-4 text-xs text-stone-500 text-center">
              No topic or speaker matches &ldquo;{q}&rdquo;.
            </div>
          ) : (
            <>
              {matches.map((t) => {
                const matchedSpeakers =
                  t.speakers?.filter((s) => matchesAllTokens(tokens, [s])) ?? [];
                return (
                  <button
                    type="button"
                    key={t.topic_id}
                    onClick={() => {
                      onSelect(t.topic_id);
                      setQ("");
                      setOpen(false);
                    }}
                    className="w-full text-left px-3 py-2.5 text-sm hover:bg-indigo-50 border-b border-stone-100 last:border-0 transition cursor-pointer"
                  >
                    <div className="text-stone-900 font-medium leading-snug">
                      {highlightMatches(t.title, tokens)}
                    </div>
                    {matchedSpeakers.length > 0 && (
                      <div className="flex items-center gap-1 flex-wrap mt-1 text-[11px] text-stone-600">
                        <Users className="w-3 h-3 text-stone-400 shrink-0" />
                        {matchedSpeakers.map((s, idx) => (
                          <span
                            key={idx}
                            className="bg-indigo-50 border border-indigo-200 text-indigo-800 rounded px-1.5 py-0.5 font-medium"
                          >
                            {highlightMatches(s, tokens)}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
              {hasMore && (
                <div className="px-3 py-2 text-[11px] text-stone-500 bg-stone-50 border-t border-stone-100 text-center">
                  Showing {matches.length} of {totalMatches} matches — refine your search to narrow down.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
