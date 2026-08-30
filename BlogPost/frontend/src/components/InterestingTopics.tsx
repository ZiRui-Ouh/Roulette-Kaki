import type { Digest } from "../types";

export default function InterestingTopics({ digest }: { digest: Digest }) {
  if (digest.interesting_topics.length === 0) return null;
  const byId = new Map(digest.topics.map((t) => [t.topic_id, t]));
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-slate-900 mb-3">
        Interesting topics
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {digest.interesting_topics.map((it) => {
          const topic = byId.get(it.topic_id);
          if (!topic) return null;
          return (
            <div
              key={it.topic_id}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="font-medium text-slate-900 mb-1">
                {topic.title}
              </div>
              <div className="text-sm text-slate-600">{it.reason}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
