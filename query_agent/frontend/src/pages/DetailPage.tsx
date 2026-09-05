import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDigest } from "../api";
import { useLanguage } from "../contexts/LanguageContext";
import type { Digest, Topic } from "../types";
import ChatPanel from "../components/ChatPanel";
import DigestSummary from "../components/DigestSummary";
import FlashcardDrawer, { type DrawerSource } from "../components/FlashcardDrawer";
import InterestingTopics from "../components/InterestingTopics";
import TopicList from "../components/TopicList";
import YoutubeThumbnail from "../components/YoutubeThumbnail";
import { ArrowLeft, RefreshCw, Calendar, AlertCircle, Play, Video, FileText } from "lucide-react";

export default function DetailPage() {
  const { date } = useParams<{ date: string }>();
  const { language } = useLanguage();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flashcardSource, setFlashcardSource] = useState<DrawerSource | null>(null);

  const openFromTopic = useCallback((t: Topic) => {
    setFlashcardSource({
      kind: "topic",
      topicId: t.topic_id,
      topicTitle: t.title,
    });
  }, []);

  const openFromChat = useCallback(
    (replyText: string, topicIdsUsed: string[]) => {
      setFlashcardSource({
        kind: "chat",
        replyText,
        topicIds: topicIdsUsed,
      });
    },
    [],
  );

  const closeDrawer = useCallback(() => setFlashcardSource(null), []);

  useEffect(() => {
    if (!date) return;
    let cancelled = false;
    setDigest(null);
    setError(null);
    getDigest(date, language)
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
  }, [date, language]);

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

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.9fr)_minmax(400px,1fr)]">
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

          {digest.youtube_url && (
            <YouTubeWatchCard url={digest.youtube_url} title={digest.title} date={digest.date} />
          )}
          <DigestSummary digest={digest} />
          <InterestingTopics digest={digest} />
          <TopicList topics={digest.topics} onGenerateFlashcards={openFromTopic} />
        </div>

        {/* Sticky Research Assistant Sidebar */}
        <aside className="lg:sticky lg:top-20 lg:self-start space-y-6">
          <ChatPanel digest={digest} onSaveReplyAsFlashcards={openFromChat} />
        </aside>
      </div>

      <FlashcardDrawer
        open={flashcardSource !== null}
        date={digest.date}
        source={flashcardSource}
        onClose={closeDrawer}
      />
    </div>
  );
}

// Parliament channel disables cross-site embedding, so the iframe path
// renders an unplayable "video unavailable" state. Instead, mirror the
// FeedPage latest-sitting spotlight: show a clickable thumbnail that
// opens the YouTube watch page in a new tab.
function YouTubeWatchCard({ url, title, date }: { url: string; title: string; date: string }) {
  const id = extractYoutubeId(url);
  if (!id) return null;
  return (
    <div className="mb-8">
      <YoutubeThumbnail
        videoId={id}
        alt={title}
        imgClassName="w-full h-full object-cover group-hover:scale-105 transition duration-500 opacity-90"
        renderReady={(img) => (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Watch on YouTube: ${title}`}
            className="group relative block rounded-2xl overflow-hidden bg-stone-900 aspect-video border border-stone-300 shadow-md cursor-pointer"
          >
            {img}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-red-600/95 flex items-center justify-center shadow-lg group-hover:scale-110 group-hover:bg-red-600 transition duration-300">
                <Play className="w-7 h-7 text-white fill-white translate-x-0.5" />
              </div>
            </div>
            <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white text-xs">
              <span className="bg-red-600 px-2 py-0.5 rounded font-bold uppercase text-[10px] tracking-wider flex items-center gap-1">
                <Video className="w-3 h-3" />
                Watch on YouTube
              </span>
              <span className="text-[11px] text-stone-300">{date}</span>
            </div>
          </a>
        )}
        fallback={
          <div className="relative rounded-2xl overflow-hidden bg-stone-100 aspect-video border border-stone-300 shadow-inner flex items-center justify-center mb-8">
            <div className="text-center text-stone-500 px-4">
              <FileText className="w-6 h-6 text-stone-500 mx-auto mb-2" />
              <div className="text-xs font-semibold">Hansard Official Record</div>
              <div className="text-[10px] text-stone-400 mt-0.5">Video preview unavailable</div>
            </div>
          </div>
        }
      />
    </div>
  );
}

function extractYoutubeId(url: string): string | null {
  // 11-char YouTube video ID with a `(?![\w-])` trailing lookahead so
  // longer stub IDs like "fixture-sitting-20260805" don't match their
  // leading 11 chars and produce a broken thumbnail URL.
  const m = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([\w-]{11})(?![\w-])/,
  );
  return m ? m[1] : null;
}
