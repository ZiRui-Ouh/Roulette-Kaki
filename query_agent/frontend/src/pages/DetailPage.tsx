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
      <div className="py-24 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto" />
        <p className="text-slate-500 text-sm">Synthesizing debate sitting digest…</p>
      </div>
    );
  }

  return (
    <div className="pb-12">
      <Link
        to="/debates"
        className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-slate-500 hover:text-indigo-600 transition mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to debates feed</span>
      </Link>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(340px,1.2fr)]">
        <div>
          <div className="mb-6">
            <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md mb-2">
              <Calendar className="w-3.5 h-3.5" />
              <span>Sitting of {digest.date}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 mt-1">
              {digest.title}
            </h1>
          </div>

          {digest.youtube_url && <YouTubeEmbed url={digest.youtube_url} />}
          <DigestSummary digest={digest} />
          <InterestingTopics digest={digest} />
          <TopicList topics={digest.topics} />
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
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
    <div className="aspect-video mb-8 rounded-xl overflow-hidden bg-black shadow-md border border-slate-200">
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
