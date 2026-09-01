import type { Digest } from "../types";
import { Lightbulb } from "lucide-react";

export default function InterestingTopics({ digest }: { digest: Digest }) {
  if (!digest.interesting_topics || digest.interesting_topics.length === 0)
    return null;
  const byId = new Map(digest.topics.map((t) => [t.topic_id, t]));

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="w-5 h-5 text-amber-500" />
        <h2 className="text-lg font-semibold text-slate-900">
          Key Highlights & Noteworthy Debates
        </h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {digest.interesting_topics.map((it) => {
          const topic = byId.get(it.topic_id);
          if (!topic) return null;
          return (
            <div
              key={it.topic_id}
              className="rounded-xl border border-amber-200/70 bg-gradient-to-br from-amber-50/50 to-white p-4 shadow-xs"
            >
              <div className="font-semibold text-slate-900 mb-1.5 text-sm sm:text-base">
                {topic.title}
              </div>
              <div className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                {it.reason}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
