import { useState } from "react";
import type { Topic } from "../types";

export default function TopicList({ topics }: { topics: Topic[] }) {
  const [filter, setFilter] = useState("");
  const q = filter.toLowerCase().trim();
  const filtered = q
    ? topics.filter((t) => t.title.toLowerCase().includes(q))
    : topics;
  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-slate-900">
          All topics ({topics.length})
        </h2>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter…"
          className="border border-slate-300 rounded-md px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
      </div>
      <div className="border border-slate-200 rounded-lg divide-y divide-slate-200 bg-white max-h-96 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="p-4 text-sm text-slate-500">No matches.</div>
        )}
        {filtered.map((t) => (
          <div key={t.topic_id} className="px-4 py-3">
            <div className="text-sm text-slate-900">{t.title}</div>
            <div className="text-xs text-slate-500 mt-1 font-mono">
              {t.topic_id}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
