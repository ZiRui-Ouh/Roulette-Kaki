import { useEffect, useState } from "react";
import { listDebates } from "../api";
import type { DebateSummary } from "../types";
import DebateCard from "../components/DebateCard";

export default function FeedPage() {
  const [debates, setDebates] = useState<DebateSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDebates()
      .then((data) => {
        if (!cancelled) setDebates(data.debates);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Failed to load feed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-900">
        {error}
      </div>
    );
  }
  if (debates === null) {
    return <p className="text-slate-500">Loading feed…</p>;
  }
  if (debates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
        <p className="text-slate-700 font-medium">No sittings cached yet.</p>
        <p className="text-slate-500 text-sm mt-2">
          Hit{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">
            GET /debates/&#123;date&#125;
          </code>{" "}
          for a real sitting date to populate the feed.
        </p>
      </div>
    );
  }
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Recent sittings</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {debates.map((d) => (
          <DebateCard key={d.date} debate={d} />
        ))}
      </div>
    </div>
  );
}
