import { Outlet } from "react-router-dom";
import Header from "./components/Header";

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-stone-50 text-slate-900 selection:bg-indigo-500 selection:text-white">
      <Header />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200/80 bg-white/70 py-6 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <span className="font-semibold text-slate-700">Roulette Kaki</span> · Singapore Policy Intelligence & Debate Digest
          </div>
          <div className="text-[11px] text-slate-400">
            Powered by Amazon Bedrock Nova Models · Sourced from Singapore Government Open Data
          </div>
        </div>
      </footer>
    </div>
  );
}