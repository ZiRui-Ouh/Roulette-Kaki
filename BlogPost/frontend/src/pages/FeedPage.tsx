import { useEffect, useState } from "react";
import { listSittings } from "../api";
import type { Sitting } from "../types";
import DebateCard from "../components/DebateCard";

const PAGE_SIZE = 5;

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
    return <p className="text-slate-500">Loading feed…</p>;
  }

  if (error?.kind === "config") {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
        <p className="text-slate-700 font-medium">Feed not configured.</p>
        <p className="text-slate-500 text-sm mt-2 mb-4">{error.message}</p>
        <p className="text-slate-500 text-sm">
          Set{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">
            YOUTUBE_PLAYLIST
          </code>{" "}
          on the backend (playlist ID or full URL) and restart uvicorn.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-900">
        {error.message}
      </div>
    );
  }

  if (sittings.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
        <p className="text-slate-700 font-medium">No sittings found.</p>
        <p className="text-slate-500 text-sm mt-2">
          The playlist appears to be empty. Double-check the ID or URL you
          set as{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">
            YOUTUBE_PLAYLIST
          </code>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Recent sittings</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sittings.map((s) => (
          <DebateCard key={s.date + s.youtube_url} debate={s} />
        ))}
      </div>
      {hasMore && (
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 hover:bg-slate-50 disabled:opacity-50"
          >
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
