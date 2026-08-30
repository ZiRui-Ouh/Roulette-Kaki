import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDigest } from "../api";
import type { Digest } from "../types";
import ChatPanel from "../components/ChatPanel";
import DigestSummary from "../components/DigestSummary";
import InterestingTopics from "../components/InterestingTopics";
import TopicList from "../components/TopicList";

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
              ? `No sitting held on ${date}.`
              : e?.message || "Failed to load digest",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [date]);

  if (error) {
    return (
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:underline">
          ← back to feed
        </Link>
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-red-900">
          {error}
        </div>
      </div>
    );
  }
  if (!digest) {
    return <p className="text-slate-500">Loading digest…</p>;
  }

  return (
    <div>
      <Link
        to="/"
        className="inline-block text-sm text-slate-500 hover:underline mb-4"
      >
        ← back to feed
      </Link>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(320px,1fr)]">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{digest.title}</h1>
          <div className="text-slate-500 mb-6">{digest.date}</div>
          {digest.youtube_url && <YouTubeEmbed url={digest.youtube_url} />}
          <DigestSummary digest={digest} />
          <InterestingTopics digest={digest} />
          <TopicList topics={digest.topics} />
        </div>
        <aside className="lg:sticky lg:top-6 lg:self-start">
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
    <div className="aspect-video mb-6 rounded-lg overflow-hidden bg-black">
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
