import { Link } from "react-router-dom";
import { Calendar, Video, ArrowRight, FileText } from "lucide-react";
import type { DebateSummary } from "../types";

export default function DebateCard({ debate }: { debate: DebateSummary }) {
  const youtubeId = extractYoutubeId(debate.youtube_url);
  return (
    <Link
      to={`/debates/${debate.date}`}
      className="group block rounded-2xl border border-stone-200 bg-white overflow-hidden hover:border-stone-400 hover:shadow-md transition duration-200 flex flex-col justify-between"
    >
      <div>
        {youtubeId ? (
          <div className="aspect-video bg-stone-900 relative overflow-hidden">
            <img
              src={`https://img.youtube.com/vi/${youtubeId}/mqdefault.jpg`}
              alt={debate.title}
              className="w-full h-full object-cover group-hover:scale-105 transition duration-300 opacity-90"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-stone-900/10 group-hover:bg-transparent transition" />
            <div className="absolute bottom-2 right-2 bg-black/80 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded backdrop-blur-xs flex items-center gap-1">
              <Video className="w-3 h-3 text-red-500" />
              <span>SPRS Recording</span>
            </div>
          </div>
        ) : (
          <div className="aspect-video bg-stone-100 flex items-center justify-center text-stone-400 text-xs">
            <FileText className="w-5 h-5 mr-1" />
            <span>Hansard Record</span>
          </div>
        )}
        <div className="p-5">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-stone-500 mb-2">
            <Calendar className="w-3.5 h-3.5 text-stone-700" />
            <span>{debate.date}</span>
          </div>
          <h3 className="font-serif font-bold text-stone-900 line-clamp-2 text-base group-hover:text-indigo-900 transition leading-snug">
            {debate.title}
          </h3>
        </div>
      </div>

      <div className="px-5 pb-5 pt-1 flex items-center justify-between text-xs font-semibold text-stone-500 group-hover:text-stone-900 border-t border-stone-100">
        <span>View full sitting digest &amp; chat</span>
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
