import { useState } from "react";
import { Search, ExternalLink, ListFilter } from "lucide-react";
import type { Topic } from "../types";

export default function TopicList({ topics }: { topics: Topic[] }) {
  const [filter, setFilter] = useState("");
  const q = filter.toLowerCase().trim();
  const filtered = q
    ? topics.filter((t) => t.title.toLowerCase().includes(q))
    : topics;

  return (
    <section className="mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <ListFilter className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-semibold text-slate-900">
            All Sitting Topics ({topics.length})
          </h2>
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search topics in this sitting…"
            className="w-full sm:w-64 pl-9 pr-3 py-1.5 text-xs sm:text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 bg-white max-h-96 overflow-y-auto shadow-xs">
        {filtered.length === 0 && (
          <div className="p-6 text-center text-sm text-slate-500">
            No matching topics found for "{filter}".
          </div>
        )}
        {filtered.map((t) => (
          <div
            key={t.topic_id}
            className="px-4 py-3 hover:bg-slate-50/80 transition flex items-start justify-between gap-4"
          >
            <div className="flex-1">
              <div className="text-sm font-medium text-slate-900">{t.title}</div>
              <div className="text-xs text-slate-400 mt-1 font-mono">
                {t.topic_id}
              </div>
            </div>

            {t.source_url && (
              <a
                href={t.source_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-slate-400 hover:text-indigo-600 p-1 rounded hover:bg-slate-100"
                title="View original SPRS source"
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
