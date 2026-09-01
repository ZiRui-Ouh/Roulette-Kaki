import { useEffect, useState } from "react";
import { listSittings } from "../api";
import type { Sitting } from "../types";
import DebateCard from "../components/DebateCard";
import { Video, RefreshCw, AlertCircle } from "lucide-react";

const PAGE_SIZE = 6;

export default function FeedPage() {
  const [sittings, setSittings] = useState<Sitting[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<
    | { kind: "config"; message: string }
    | { kind: "other"; message: string }
    | null
  >(null);

  // Initial load on mount.
  useEffect(() => {
    let cancelled = false;
    listSittings(PAGE_SIZE, 0)
      .then((data) => {
        if (cancelled) return;
        setSittings(data.sittings);
        setOffset(data.sittings.length);
        setHasMore(data.has_more);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e?.error === "sittings_unavailable") {
          setError({ kind: "config", message: e.message });
        } else {
          setError({ kind: "other", message: e?.message || "Failed to load feed" });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const data = await listSittings(PAGE_SIZE, offset);
      setSittings((prev) => [...prev, ...data.sittings]);
      setOffset(offset + data.sittings.length);
      setHasMore(data.has_more);
    } catch (e) {
      const err = e as { message?: string };
      setError({
        kind: "other",
        message: err?.message || "Failed to load more sittings",
      });
    } finally {
      setLoadingMore(false);
    }
  }

  if (loading) {
    return (
      <div className="py-20 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto" />
        <p className="text-slate-500 text-sm">Loading parliament debate sittings…</p>
      </div>
    );
  }

  if (error?.kind === "config") {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center max-w-xl mx-auto my-8 shadow-xs">
        <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-3">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-slate-800 font-semibold text-base">Parliament Feed Not Configured</h2>
        <p className="text-slate-500 text-sm mt-2 mb-4 leading-relaxed">{error.message}</p>
        <p className="text-slate-500 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
          Set <code className="font-mono text-indigo-600 font-semibold">YOUTUBE_PLAYLIST</code> on the backend environment and restart the API server.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 max-w-xl mx-auto my-8">
        <h3 className="font-semibold text-sm mb-1">Failed to connect to debate service</h3>
        <p className="text-xs text-red-700">{error.message}</p>
      </div>
    );
  }

  if (sittings.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center max-w-xl mx-auto my-8 shadow-xs">
        <Video className="w-10 h-10 text-slate-300 mx-auto mb-2" />
        <p className="text-slate-700 font-semibold">No debate sittings recorded yet.</p>
        <p className="text-slate-500 text-xs mt-1">
          Check back after the next scheduled Singapore Parliament sitting.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-6 border-b border-slate-200 mb-6 gap-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Parliament Debate Digest
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Explore sitting transcripts, automated summarization, and key policy debate highlights.
          </p>
        </div>
        <div className="text-xs text-slate-500 font-medium">
          Showing {sittings.length} sitting dates
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {sittings.map((s) => (
          <DebateCard key={s.date + s.youtube_url} debate={s} />
        ))}
      </div>

      {hasMore && (
        <div className="mt-8 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50 transition shadow-xs inline-flex items-center gap-2"
          >
            {loadingMore ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
                <span>Loading more sittings…</span>
              </>
            ) : (
              <span>Load earlier sittings</span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
