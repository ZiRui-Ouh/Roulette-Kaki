import { Link } from "react-router-dom";
import { Calendar, Video, ArrowRight } from "lucide-react";
import type { DebateSummary } from "../types";

export default function DebateCard({ debate }: { debate: DebateSummary }) {
  const youtubeId = extractYoutubeId(debate.youtube_url);
  return (
    <Link
      to={`/debates/${debate.date}`}
      className="group block rounded-xl border border-slate-200 bg-white overflow-hidden hover:border-indigo-300 hover:shadow-md transition duration-200 flex flex-col justify-between"
    >
      <div>
        {youtubeId ? (
          <div className="aspect-video bg-slate-100 relative overflow-hidden">
            <img
              src={`https://img.youtube.com/vi/${youtubeId}/mqdefault.jpg`}
              alt={debate.title}
              className="w-full h-full object-cover group-hover:scale-102 transition duration-300"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-slate-900/10 group-hover:bg-slate-900/0 transition" />
            <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[11px] px-2 py-0.5 rounded backdrop-blur-xs flex items-center gap-1">
              <Video className="w-3 h-3" />
              <span>SPRS Recording</span>
            </div>
          </div>
        ) : (
          <div className="aspect-video bg-slate-100 flex items-center justify-center text-slate-400 text-sm">
            No video recording
          </div>
        )}
        <div className="p-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-600 mb-2">
            <Calendar className="w-3.5 h-3.5" />
            <span>{debate.date}</span>
          </div>
          <h3 className="font-semibold text-slate-900 line-clamp-2 text-base group-hover:text-indigo-600 transition">
            {debate.title}
          </h3>
        </div>
      </div>

      <div className="px-4 pb-4 pt-1 flex items-center justify-between text-xs font-medium text-slate-500 group-hover:text-indigo-600">
        <span>View full sitting digest</span>
        <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
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
