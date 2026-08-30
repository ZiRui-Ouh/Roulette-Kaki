import type { Digest } from "../types";

export default function DigestSummary({ digest }: { digest: Digest }) {
  const cats = Object.entries(digest.category_breakdown);
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-slate-900 mb-2">Summary</h2>
      <p className="text-slate-700 leading-relaxed mb-4 whitespace-pre-wrap">
        {digest.summary}
      </p>
      {cats.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-2">
            Topics by category ({digest.topic_count} total)
          </h3>
          <div className="flex flex-wrap gap-2">
            {cats.map(([cat, count]) => (
              <span
                key={cat}
                className="text-sm bg-slate-100 text-slate-700 rounded-full px-3 py-1"
              >
                {cat} · {count}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
