import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listSittings } from "../api";
import type { Sitting } from "../types";
import DebateCard from "../components/DebateCard";
import YoutubeThumbnail from "../components/YoutubeThumbnail";
import { Video, RefreshCw, FileText, ArrowRight, ShieldCheck, Sparkles, Building2, AlertCircle, Play } from "lucide-react";

const PAGE_SIZE = 6;

export default function FeedPage() {
  // The feed starts with the newest parliamentary sittings and keeps the
  // pagination position so the user can request older records on demand.
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
    // The cancellation flag prevents a slow response from updating a page
    // that the user has already left.
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
          setError({
            kind: "other",
            message: e?.message || "Failed to load parliament sittings",
          });
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
    // Pagination stops while another request is running or when the backend
    // says that there are no more sittings.
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const data = await listSittings(PAGE_SIZE, offset);
      setSittings((prev) => [...prev, ...data.sittings]);
      setOffset(offset + data.sittings.length);
      setHasMore(data.has_more);
    } catch (e) {
      const err = e as { error?: string; message?: string };
      if (err?.error === "sittings_unavailable") {
        setError({ kind: "config", message: err.message || "Sittings feed unavailable" });
      } else {
        setError({
          kind: "other",
          message: err?.message || "Failed to load more sittings",
        });
      }
    } finally {
      setLoadingMore(false);
    }
  }

  if (loading) {
    return (
      <div className="py-24 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-stone-600 animate-spin mx-auto" />
        <p className="text-stone-500 text-sm font-serif italic">Compiling Hansard parliamentary sittings…</p>
      </div>
    );
  }

  if (error?.kind === "config" && sittings.length === 0) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 max-w-xl mx-auto my-12 shadow-xs text-center">
        <AlertCircle className="w-8 h-8 text-amber-600 mx-auto mb-2" />
        <h3 className="font-semibold text-sm mb-1">Sittings Feed Not Configured</h3>
        <p className="text-xs text-amber-800 mb-3">{error.message}</p>
        <p className="text-xs text-amber-700">
          Set{" "}
          <code className="bg-amber-100 px-1.5 py-0.5 rounded text-[11px] font-mono">
            YOUTUBE_PLAYLIST
          </code>{" "}
          on the backend (playlist ID or full URL) and restart uvicorn.
        </p>
      </div>
    );
  }

  if (error && sittings.length === 0) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 max-w-xl mx-auto my-12 shadow-xs text-center">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h3 className="font-semibold text-sm mb-1">Unable to Load Parliament Sittings</h3>
        <p className="text-xs text-red-700">{error.message}</p>
      </div>
    );
  }

  if (sittings.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center max-w-xl mx-auto my-12 shadow-xs">
        <FileText className="w-8 h-8 text-stone-500 mx-auto mb-3" />
        <h3 className="font-serif font-bold text-base text-stone-900 mb-1">No Sittings Found</h3>
        <p className="text-xs text-stone-600 leading-relaxed">
          The playlist appears to be empty. Double-check the ID or URL you set as{" "}
          <code className="bg-stone-100 px-1.5 py-0.5 rounded text-[11px] font-mono">
            YOUTUBE_PLAYLIST
          </code>
          .
        </p>
      </div>
    );
  }

  const latestSitting = sittings.length > 0 ? sittings[0] : null;
  const earlierSittings = sittings.length > 1 ? sittings.slice(1) : [];
  const latestYoutubeId = latestSitting?.youtube_url
    ? extractYoutubeId(latestSitting.youtube_url)
    : null;

  return (
    <div className="space-y-10 pb-16">
      {/* Editorial Header */}
      <section className="border-b border-stone-200 pb-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-stone-500 mb-1">
              <Building2 className="w-4 h-4 text-stone-700" />
              <span>Parliament of Singapore &bull; Official Hansard Gazette</span>
            </div>
            <h1 className="font-serif font-black text-3xl sm:text-4xl text-stone-900 tracking-tight">
              Parliament Debate Digest &amp; Sittings
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-stone-600 max-w-2xl">
              Explore sitting transcripts, automated debate synthesis, and ministerial Q&amp;As across the Singapore Legislative Assembly.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-stone-500 font-medium">
            <span className="flex items-center gap-1 bg-stone-100 px-3 py-1.5 rounded-lg border border-stone-200">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Verified SPRS Records</span>
            </span>
            <span className="flex items-center gap-1 bg-stone-100 px-3 py-1.5 rounded-lg border border-stone-200">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>Nova AI Synthesis</span>
            </span>
          </div>
        </div>
      </section>

      {/* Spotlight: Latest Sitting Cover Card */}
      {latestSitting && (
        <section>
          <div className="flex items-center gap-2 pb-2.5 mb-4 border-b border-stone-200 text-xs font-bold uppercase tracking-wider text-stone-900">
            <span className="w-2.5 h-2.5 bg-red-600 rounded-full animate-pulse"></span>
            <span>Latest Sitting Dispatch</span>
          </div>

          <div className="bg-white rounded-2xl border border-stone-300 p-6 sm:p-8 shadow-xs hover:shadow-md transition">
            <div className="grid gap-6 md:grid-cols-[1.2fr_1fr] items-center">
              <div>
                <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-600 bg-stone-100 px-2.5 py-1 rounded-md mb-3 border border-stone-200">
                  <FileText className="w-3.5 h-3.5 text-stone-700" />
                  <span>Sitting of {latestSitting.date}</span>
                </div>
                <h2 className="font-serif font-bold text-2xl sm:text-3xl text-stone-900 leading-tight">
                  {latestSitting.title}
                </h2>
                <p className="text-xs sm:text-sm text-stone-600 mt-3 leading-relaxed">
                  Full legislative synthesis covering ministerial responses, oral debate motions, and bill readings recorded in official Hansard transcripts.
                </p>

                <div className="mt-6 flex items-center gap-3">
                  <Link
                    to={`/debates/${latestSitting.date}`}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-stone-900 hover:bg-stone-800 text-white text-xs sm:text-sm font-semibold transition shadow-xs"
                  >
                    <span>Read Sitting Digest &amp; Consult Assistant</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>

              {/* YouTube Thumbnail — links to the watch page in a new tab
                  (YouTube disables cross-site embedding for this channel).
                  Falls back to a static card when the video is missing,
                  removed, or an unrecognised stub. */}
              <YoutubeThumbnail
                videoId={latestYoutubeId}
                alt={latestSitting.title}
                imgClassName="w-full h-full object-cover group-hover:scale-105 transition duration-500 opacity-90"
                renderReady={(img) => (
                  <a
                    href={latestSitting.youtube_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Watch on YouTube: ${latestSitting.title}`}
                    className="group relative block rounded-xl overflow-hidden bg-stone-900 aspect-video border border-stone-200 shadow-inner cursor-pointer"
                  >
                    {img}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-14 h-14 rounded-full bg-red-600/95 flex items-center justify-center shadow-lg group-hover:scale-110 group-hover:bg-red-600 transition duration-300">
                        <Play className="w-6 h-6 text-white fill-white translate-x-0.5" />
                      </div>
                    </div>
                    <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white text-xs">
                      <span className="bg-red-600 px-2 py-0.5 rounded font-bold uppercase text-[10px] tracking-wider flex items-center gap-1">
                        <Video className="w-3 h-3" />
                        SPRS Broadcast
                      </span>
                      <span className="text-[11px] text-stone-300">
                        {latestSitting.date}
                      </span>
                    </div>
                  </a>
                )}
                fallback={
                  <div className="relative rounded-xl overflow-hidden bg-stone-100 aspect-video border border-stone-200 shadow-inner flex items-center justify-center">
                    <div className="text-center text-stone-500 px-4">
                      <FileText className="w-6 h-6 text-stone-500 mx-auto mb-2" />
                      <div className="text-xs font-semibold">Hansard Official Record</div>
                      <div className="text-[10px] text-stone-400 mt-0.5">
                        Video preview unavailable
                      </div>
                    </div>
                  </div>
                }
              />
            </div>
          </div>
        </section>
      )}

      {/* Sittings Archive Grid */}
      {earlierSittings.length > 0 && (
        <section className="pt-4 border-t border-stone-200">
          <div className="flex items-center justify-between pb-4 mb-6 border-b border-stone-200">
            <h2 className="font-serif font-bold text-xl sm:text-2xl text-stone-900">
              Sitting Archives &amp; Transcripts
            </h2>
            <div className="text-xs text-stone-500 font-medium">
              Showing {sittings.length} total sittings
            </div>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {earlierSittings.map((s) => (
              <DebateCard key={s.date + s.youtube_url} debate={s} />
            ))}
          </div>

          {hasMore && (
            <div className="mt-10 text-center">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-xl border border-stone-300 bg-white px-5 py-2.5 text-xs font-semibold text-stone-700 hover:bg-stone-50 hover:text-stone-900 disabled:opacity-50 transition shadow-xs inline-flex items-center gap-2 cursor-pointer"
              >
                {loadingMore ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-stone-600" />
                    <span>Loading earlier sittings…</span>
                  </>
                ) : (
                  <span>Load Earlier Sittings</span>
                )}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function extractYoutubeId(url: string): string | null {
  // Match a real 11-char YouTube video ID. The trailing `(?![\w-])`
  // negative lookahead is essential — without it, longer stub IDs like
  // "fixture-sitting-20260805" match their first 11 chars and produce a
  // broken YouTube thumbnail URL.
  const m = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([\w-]{11})(?![\w-])/,
  );
  return m ? m[1] : null;
}
