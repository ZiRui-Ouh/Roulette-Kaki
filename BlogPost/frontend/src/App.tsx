import { Link, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-baseline justify-between">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            Parliament Debate Digest
          </Link>
          <span className="text-xs text-slate-400 hidden sm:inline">
            Singapore · AI-generated summaries
          </span>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
