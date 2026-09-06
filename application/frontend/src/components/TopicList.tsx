import { useMemo, useState } from "react";
import { Search, ExternalLink, ListFilter, Users, Layers, X } from "lucide-react";
import type { Topic } from "../types";
import { highlightMatches, tokenize, matchesAllTokens } from "../lib/textMatch";

interface Props {
  topics: Topic[];
  onGenerateFlashcards?: (topic: Topic) => void;
}

export default function TopicList({ topics, onGenerateFlashcards }: Props) {
  const [filter, setFilter] = useState("");

  // Dedup by topic_id — the backend has occasionally returned duplicate
  // entries (SPRS pagination overshoot). Without this, React warns about
  // duplicate keys AND its reconciler drops updates, which manifests as
  // the filter appearing to freeze after a few keystrokes.
  const uniqueTopics = useMemo(() => {
    const seen = new Set<string>();
    return topics.filter((t) => {
      if (!t.topic_id || seen.has(t.topic_id)) return false;
      seen.add(t.topic_id);
      return true;
    });
  }, [topics]);

  const tokens = useMemo(() => tokenize(filter), [filter]);
  const filtered = useMemo(() => {
    if (!tokens.length) return uniqueTopics;
    return uniqueTopics.filter((t) =>
      matchesAllTokens(tokens, [t.title, ...(t.speakers ?? [])]),
    );
  }, [uniqueTopics, tokens]);

  const filtering = tokens.length > 0;

  return (
    <section className="mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <ListFilter className="w-5 h-5 text-stone-700" />
          <h2 className="font-serif font-bold text-lg text-stone-900">
            Sitting Agenda &amp; Hansard Topics{" "}
            <span className="text-stone-500 font-sans font-normal text-sm">
              ({filtering ? `${filtered.length} of ${uniqueTopics.length}` : uniqueTopics.length})
            </span>
          </h2>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter topics or speakers…"
            className="w-full sm:w-72 pl-8 pr-8 py-1.5 text-xs border border-stone-300 rounded-lg bg-white text-stone-800 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition shadow-2xs"
          />
          {filter && (
            <button
              type="button"
              onClick={() => setFilter("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 p-0.5 cursor-pointer"
              title="Clear filter"
              aria-label="Clear filter"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="border border-stone-200 rounded-2xl divide-y divide-stone-100 bg-white max-h-96 overflow-y-auto shadow-xs">
        {filtered.length === 0 && (
          <div className="p-8 text-center text-xs text-stone-500">
            No topic or speaker matches &ldquo;{filter}&rdquo;.
          </div>
        )}
        {filtered.map((t) => (
          <div
            key={t.topic_id}
            className="p-4 hover:bg-stone-50/80 transition flex items-start justify-between gap-4"
          >
            <div className="flex-1">
              <div className="text-xs sm:text-sm font-semibold text-stone-900 leading-snug">
                {highlightMatches(t.title, tokens)}
              </div>

              {t.speakers && t.speakers.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap mt-1.5 text-[11px] text-stone-500">
                  <Users className="w-3 h-3 text-stone-400 shrink-0" />
                  <span className="font-medium text-stone-700">Speakers:</span>
                  {t.speakers.map((spk, idx) => {
                    const speakerMatched =
                      tokens.length > 0 && matchesAllTokens(tokens, [spk]);
                    return (
                      <span
                        key={idx}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                          speakerMatched
                            ? "bg-indigo-50 text-indigo-800 border-indigo-200"
                            : "bg-stone-100 text-stone-700 border-stone-200/60"
                        }`}
                      >
                        {highlightMatches(spk, tokens)}
                      </span>
                    );
                  })}
                </div>
              )}

              <div className="text-[10px] text-stone-400 mt-1 font-mono">
                {t.topic_id}
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-0.5">
              {onGenerateFlashcards && (
                <button
                  type="button"
                  onClick={() => onGenerateFlashcards(t)}
                  className="text-stone-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-stone-100 transition cursor-pointer"
                  title="Generate flashcards for this topic"
                  aria-label="Generate flashcards"
                >
                  <Layers className="w-4 h-4" />
                </button>
              )}
              {t.source_url && (
                <a
                  href={t.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-stone-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-stone-100 transition"
                  title="View original Hansard SPRS source transcript"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
