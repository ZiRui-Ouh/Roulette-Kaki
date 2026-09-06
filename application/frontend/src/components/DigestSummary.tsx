import type { Digest } from "../types";
import { Sparkles, Layers } from "lucide-react";

// Presents the digest text and category counts returned by the backend.
export default function DigestSummary({ digest }: { digest: Digest }) {
  const cats = Object.entries(digest.category_breakdown || {});
  return (
    <section className="mb-8 rounded-2xl border border-stone-200 bg-white p-6 sm:p-7 shadow-xs">
      <div className="flex items-center gap-2 text-stone-900 font-serif font-bold text-lg mb-3">
        <Sparkles className="w-5 h-5 text-indigo-600" />
        <h2>Executive Debate Summary</h2>
      </div>

      <p className="text-stone-700 leading-relaxed mb-6 whitespace-pre-wrap text-xs sm:text-sm font-sans">
        {digest.summary}
      </p>

      {cats.length > 0 && (
        <div className="pt-4 border-t border-stone-100">
          <div className="flex items-center gap-1.5 text-[11px] font-bold text-stone-500 uppercase tracking-wider mb-3">
            <Layers className="w-3.5 h-3.5 text-stone-600" />
            <span>Debate Agenda by Category ({digest.topic_count} items debated)</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {cats.map(([cat, count]) => (
              <span
                key={cat}
                className="text-xs font-semibold bg-stone-100 text-stone-800 rounded-lg px-3 py-1.5 border border-stone-200"
              >
                {cat} · <span className="text-indigo-600 font-bold">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
