import { useState } from "react";
import { Search, ExternalLink, ListFilter, Users } from "lucide-react";
import type { Topic } from "../types";

export default function TopicList({ topics }: { topics: Topic[] }) {
  const [filter, setFilter] = useState("");
  const q = filter.toLowerCase().trim();
  const filtered = q
    ? topics.filter((t) => 
        t.title.toLowerCase().includes(q) || 
        (t.speakers && t.speakers.some(s => s.toLowerCase().includes(q)))
      )
    : topics;

  return (
    <section className="mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <ListFilter className="w-5 h-5 text-stone-700" />
          <h2 className="font-serif font-bold text-lg text-stone-900">
            Sitting Agenda &amp; Hansard Topics ({topics.length})
          </h2>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter topics or speakers…"
            className="w-full sm:w-64 pl-8 pr-3 py-1.5 text-xs border border-stone-300 rounded-lg bg-white text-stone-800 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition shadow-2xs"
          />
        </div>
      </div>

      <div className="border border-stone-200 rounded-2xl divide-y divide-stone-100 bg-white max-h-96 overflow-y-auto shadow-xs">
        {filtered.length === 0 && (
          <div className="p-8 text-center text-xs text-stone-500">
            No matching topics found for "{filter}".
          </div>
        )}
        {filtered.map((t) => (
          <div
            key={t.topic_id}
            className="p-4 hover:bg-stone-50/80 transition flex items-start justify-between gap-4"
          >
            <div className="flex-1">
              <div className="text-xs sm:text-sm font-semibold text-stone-900 leading-snug">
                {t.title}
              </div>
              
              {t.speakers && t.speakers.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap mt-1.5 text-[11px] text-stone-500">
                  <Users className="w-3 h-3 text-stone-400 shrink-0" />
                  <span className="font-medium text-stone-700">Speakers:</span>
                  {t.speakers.map((spk, idx) => (
                    <span
                      key={idx}
                      className="bg-stone-100 text-stone-700 px-2 py-0.5 rounded text-[10px] font-medium border border-stone-200/60"
                    >
                      {spk}
                    </span>
                  ))}
                </div>
              )}

              <div className="text-[10px] text-stone-400 mt-1 font-mono">
                {t.topic_id}
              </div>
            </div>

            {t.source_url && (
              <a
                href={t.source_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-stone-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-stone-100 transition"
                title="View original Hansard SPRS source transcript"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
