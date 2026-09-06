import { Link, useLocation } from "react-router-dom";
import { MessageSquareText, FileText } from "lucide-react";

// Shared legacy header used by screens that need simple application branding.
export default function Header() {
  const location = useLocation();

  const isQueryActive =
    location.pathname === "/" || location.pathname.startsWith("/query");
  const isDebatesActive = location.pathname.startsWith("/debates");

  return (
    <header className="sticky top-0 z-30 bg-slate-900/95 backdrop-blur border-b border-slate-800 text-white shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-semibold tracking-tight text-white hover:text-slate-200 transition"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-emerald-400 flex items-center justify-center text-white font-bold text-base shadow-sm">
              SG
            </div>
            <div>
              <span className="font-bold">The Singapore Chronicles</span>
              <span className="text-xs font-normal text-slate-400 ml-2 hidden md:inline">
                Singapore Policy & Debate Intelligence
              </span>
            </div>
          </Link>
        </div>

        <nav className="flex items-center gap-1.5 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 self-start sm:self-auto">
          <Link
            to="/"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition ${
              isQueryActive
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-300 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            <MessageSquareText className="w-4 h-4" />
            <span>Policy Query</span>
            <span className="flex h-1.5 w-1.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
            </span>
          </Link>

          <Link
            to="/debates"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition ${
              isDebatesActive
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-300 hover:text-white hover:bg-slate-700/50"
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Debate Digest</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
