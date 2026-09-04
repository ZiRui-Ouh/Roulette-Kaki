import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDigest } from "../api";
import type { Digest } from "../types";
import ChatPanel from "../components/ChatPanel";
import DigestSummary from "../components/DigestSummary";
import InterestingTopics from "../components/InterestingTopics";
import TopicList from "../components/TopicList";
import { ArrowLeft, RefreshCw, Calendar, AlertCircle } from "lucide-react";

export default function DetailPage() {
  const { date } = useParams<{ date: string }>();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!date) return;
    let cancelled = false;
    setDigest(null);
    setError(null);
    getDigest(date)
      .then((d) => {
        if (!cancelled) setDigest(d);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(
            e?.status === 404
              ? `No parliament sitting was held on ${date}.`
              : e?.message || "Failed to load debate sitting digest",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [date]);

  if (error) {
    return (
      <div className="py-6 space-y-4 max-w-2xl mx-auto">
        <Link
          to="/debates"
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-slate-500 hover:text-indigo-600 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to debates feed</span>
        </Link>
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-900 flex items-start gap-3 shadow-xs">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-sm">Notice</h3>
            <p className="text-xs text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!digest) {
    return (
      <div className="py-28 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-stone-600 animate-spin mx-auto" />
        <p className="text-stone-500 text-sm font-serif italic">Synthesizing debate sitting digest &amp; Hansard records…</p>
      </div>
    );
  }

  return (
    <div className="pb-16 max-w-7xl mx-auto">
      {/* Top Breadcrumb & Metadata Navigation */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-stone-200">
        <Link
          to="/debates"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-500 hover:text-stone-900 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Parliamentary Sittings Archive</span>
        </Link>
        <span className="text-[11px] text-stone-400 font-sans">
          SPRS Official Record &bull; Singapore Legislative Assembly
        </span>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(350px,1.2fr)]">
        <div>
          {/* Sitting Masthead */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-600 bg-stone-100 px-3 py-1 rounded-md mb-3 border border-stone-200">
              <Calendar className="w-3.5 h-3.5 text-stone-700" />
              <span>Sitting of {digest.date}</span>
            </div>
            <h1 className="font-serif font-black text-2xl sm:text-3xl md:text-4xl text-stone-900 tracking-tight leading-tight">
              {digest.title}
            </h1>
            <p className="text-xs text-stone-500 mt-2 font-sans">
              Official Legislative Record &bull; {digest.topic_count} Topics Debated &bull; Hansard Verified
            </p>
          </div>

          {digest.youtube_url && <YouTubeEmbed url={digest.youtube_url} />}
          <DigestSummary digest={digest} />
          <InterestingTopics digest={digest} />
          <TopicList topics={digest.topics} />
        </div>

        {/* Sticky Research Assistant Sidebar */}
        <aside className="lg:sticky lg:top-20 lg:self-start space-y-6">
          <ChatPanel digest={digest} />
        </aside>
      </div>
    </div>
  );
}

function YouTubeEmbed({ url }: { url: string }) {
  const id = extractYoutubeId(url);
  if (!id) return null;
  return (
    <div className="aspect-video mb-8 rounded-2xl overflow-hidden bg-black shadow-md border border-stone-300">
      <iframe
        className="w-full h-full"
        src={`https://www.youtube.com/embed/${id}`}
        title="Sitting livestream"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}

function extractYoutubeId(url: string): string | null {
  const m = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([\w-]{11})/,
  );
  return m ? m[1] : null;
}
