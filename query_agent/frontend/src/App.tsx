import { useState } from "react";
import { Outlet } from "react-router-dom";
import NewsHeader from "./components/NewsHeader";
import type { PolicyCategory } from "./types";

export interface OutletContextType {
  selectedCategory: PolicyCategory | "All";
  setSelectedCategory: (cat: PolicyCategory | "All") => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export default function App() {
  const [selectedCategory, setSelectedCategory] =
    useState<PolicyCategory | "All">("All");
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <div className="min-h-screen flex flex-col bg-[#fdfcfb] text-stone-900 selection:bg-indigo-600 selection:text-white font-sans antialiased">
      <NewsHeader
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <Outlet
          context={{
            selectedCategory,
            setSelectedCategory,
            searchQuery,
            setSearchQuery,
          }}
        />
      </main>
      <footer className="border-t border-stone-200 bg-white py-8 text-xs text-stone-500 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="font-serif font-black text-sm text-stone-800 tracking-tight">
              THE SINGAPORE CHRONICLES
            </div>
            <div className="text-[11px] text-stone-400 mt-0.5">
              Empowering citizens with transparent, AI-verified public policy &amp; legislative intelligence.
            </div>
          </div>
          <div className="text-[11px] text-stone-400 text-center sm:text-right">
            <div>
              Built for Singapore Citizens &bull; Powered by Amazon Bedrock Nova Lite
            </div>
            <div className="mt-0.5">
              All policy facts cross-referenced against official Singapore Government gazettes (.gov.sg)
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}