import { Link } from "react-router-dom";
import type { DebateSummary } from "../types";

export default function DebateCard({ debate }: { debate: DebateSummary }) {
  const youtubeId = extractYoutubeId(debate.youtube_url);
  return (
    <Link
      to={`/debates/${debate.date}`}
      className="block rounded-lg border border-slate-200 bg-white overflow-hidden hover:border-slate-400 hover:shadow-sm transition"
    >
      {youtubeId ? (
        <div className="aspect-video bg-slate-100">
          <img
            src={`https://img.youtube.com/vi/${youtubeId}/mqdefault.jpg`}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      ) : (
        <div className="aspect-video bg-slate-100 flex items-center justify-center text-slate-400 text-sm">
          No video
        </div>
      )}
      <div className="p-4">
        <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
          {debate.date}
        </div>
        <div className="font-medium text-slate-900">{debate.title}</div>
      </div>
    </Link>
  );
}

function extractYoutubeId(url: string): string | null {
  const m = url.match(
    /(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([\w-]{11})/,
  );
  return m ? m[1] : null;
}
