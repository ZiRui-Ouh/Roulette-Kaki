import type { Digest } from "../types";
import { Lightbulb } from "lucide-react";

function dedupById<T extends { topic_id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((it) => {
    if (!it.topic_id || seen.has(it.topic_id)) return false;
    seen.add(it.topic_id);
    return true;
  });
}

// Shows the topics the digest agent selected as especially noteworthy.
export default function InterestingTopics({ digest }: { digest: Digest }) {
  if (!digest.interesting_topics || digest.interesting_topics.length === 0)
    return null;
  const byId = new Map(digest.topics.map((t) => [t.topic_id, t]));

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="w-5 h-5 text-amber-600" />
        <h2 className="font-serif font-bold text-lg text-stone-900">
          Key Highlights &amp; Noteworthy Parliamentary Debates
        </h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {dedupById(digest.interesting_topics).map((it) => {
          const topic = byId.get(it.topic_id);
          if (!topic) return null;
          return (
            <div
              key={it.topic_id}
              className="rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50/40 via-white to-white p-5 shadow-xs"
            >
              <div className="font-serif font-bold text-stone-900 mb-1.5 text-sm sm:text-base leading-snug">
                {topic.title}
              </div>
              <div className="text-xs text-stone-600 leading-relaxed font-sans">
                {it.reason}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
