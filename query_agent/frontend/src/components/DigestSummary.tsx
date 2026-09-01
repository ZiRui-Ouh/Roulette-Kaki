import type { Digest } from "../types";
import { Sparkles, Layers } from "lucide-react";

export default function DigestSummary({ digest }: { digest: Digest }) {
  const cats = Object.entries(digest.category_breakdown || {});
  return (
    <section className="mb-8 rounded-xl border border-slate-200/90 bg-white p-6 shadow-xs">
      <div className="flex items-center gap-2 text-indigo-700 font-semibold mb-3">
        <Sparkles className="w-5 h-5 text-indigo-600" />
        <h2 className="text-lg text-slate-900">Debate Summary</h2>
      </div>

      <p className="text-slate-700 leading-relaxed mb-6 whitespace-pre-wrap text-sm sm:text-base">
        {digest.summary}
      </p>

      {cats.length > 0 && (
        <div className="pt-4 border-t border-slate-100">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            <Layers className="w-3.5 h-3.5" />
            <span>Topics by category ({digest.topic_count} total)</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {cats.map(([cat, count]) => (
              <span
                key={cat}
                className="text-xs font-medium bg-slate-100 text-slate-700 rounded-lg px-3 py-1.5 border border-slate-200/60"
              >
                {cat} · <span className="text-indigo-600 font-semibold">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
