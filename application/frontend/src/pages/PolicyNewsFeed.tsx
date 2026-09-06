import { useMemo } from "react";
import { Link, useOutletContext } from "react-router-dom";
import {
  TrendingUp,
  FileText,
  Sparkles,
  ArrowRight,
  Search,
} from "lucide-react";
import { POLICIES } from "../data/policies";
import type { PolicyCategory } from "../types";
import PolicyHeroCard from "../components/PolicyHeroCard";
import PolicyNewsCard from "../components/PolicyNewsCard";

interface OutletContextType {
  selectedCategory: PolicyCategory | "All";
  setSelectedCategory: (cat: PolicyCategory | "All") => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export default function PolicyNewsFeed() {
  // The home page presents the local policy feed. Category and search state
  // come from App so the header and feed stay synchronized.
  const outletCtx = useOutletContext<OutletContextType>() || {
    selectedCategory: "All",
    setSelectedCategory: () => {},
    searchQuery: "",
    setSearchQuery: () => {},
  };

  const { selectedCategory, setSelectedCategory, searchQuery } = outletCtx;

  // Filter policies based on category and search query
  const filteredPolicies = useMemo(() => {
    return POLICIES.filter((p) => {
      const matchesCategory =
        selectedCategory === "All" || p.category === selectedCategory;
      const query = (searchQuery || "").toLowerCase().trim();
      const matchesSearch =
        !query ||
        p.title.toLowerCase().includes(query) ||
        p.headline.toLowerCase().includes(query) ||
        p.summary.toLowerCase().includes(query) ||
        p.ministry.toLowerCase().includes(query) ||
        p.category.toLowerCase().includes(query);

      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  const heroPolicy = filteredPolicies.length > 0 ? filteredPolicies[0] : null;
  const secondaryPolicies =
    filteredPolicies.length > 1 ? filteredPolicies.slice(1) : [];

  return (
    <div className="pb-16 max-w-7xl mx-auto space-y-10">
      {/* Frontpage Editorial Lead Story */}
      {heroPolicy ? (
        <section>
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-stone-200">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-red-600 rounded-full animate-pulse"></span>
              <h2 className="text-xs font-bold uppercase tracking-wider text-stone-900 font-sans">
                {selectedCategory === "All"
                  ? "Top Gazette Cover Story"
                  : `${selectedCategory} Lead Dispatch`}
              </h2>
            </div>
            <div className="text-xs text-stone-500 font-medium">
              Showing {filteredPolicies.length} of {POLICIES.length} policies
            </div>
          </div>

          <PolicyHeroCard policy={heroPolicy} />
        </section>
      ) : (
        <div className="bg-white rounded-2xl border border-dashed border-stone-300 p-12 text-center max-w-lg mx-auto shadow-xs">
          <Search className="w-10 h-10 text-stone-400 mx-auto mb-3" />
          <h3 className="text-base font-bold text-stone-900">No Policies Match Your Search</h3>
          <p className="text-xs text-stone-500 mt-1 mb-4">
            Try adjusting your query or resetting the category filter.
          </p>
          <button
            type="button"
            onClick={() => setSelectedCategory("All")}
            className="px-4 py-2 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 transition cursor-pointer"
          >
            Reset All Filters
          </button>
        </div>
      )}

      {/* Main Grid Section: Secondary Policy Cards + News Sidebar */}
      {secondaryPolicies.length > 0 && (
        <section className="pt-4 border-t border-stone-200">
          <div className="flex items-center justify-between pb-4 mb-6 border-b border-stone-200">
            <h2 className="font-serif font-black text-xl sm:text-2xl text-stone-900">
              Recent Policy Dispatches &amp; Circulars
            </h2>
            <span className="text-xs text-stone-500 hidden sm:inline">
              Interactive AI Consultation Available On Every Article
            </span>
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
            {/* Policy Grid */}
            <div className="grid gap-6 sm:grid-cols-2">
              {secondaryPolicies.map((policy) => (
                <PolicyNewsCard key={policy.id} policy={policy} />
              ))}
            </div>

            {/* Editorial Sidebar */}
            <aside className="space-y-6">
              {/* Trending Inquiries Box */}
              <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs">
                <div className="flex items-center gap-2 pb-3 mb-3 border-b border-stone-100 text-xs font-bold uppercase tracking-wider text-stone-900">
                  <TrendingUp className="w-4 h-4 text-indigo-600" />
                  <span>Most Inquired Policies</span>
                </div>

                <div className="space-y-3">
                  {POLICIES.slice(0, 4).map((p, idx) => (
                    <Link
                      key={p.id}
                      to={`/policy/${p.id}`}
                      className="group block p-2 rounded-xl hover:bg-stone-50 transition"
                    >
                      <div className="flex items-start gap-2.5">
                        <span className="font-serif font-bold text-stone-300 group-hover:text-indigo-600 text-sm">
                          0{idx + 1}
                        </span>
                        <div>
                          <div className="text-xs font-semibold text-stone-800 group-hover:text-indigo-600 line-clamp-2 transition leading-snug">
                            {p.headline}
                          </div>
                          <div className="text-[10px] text-stone-400 mt-0.5">
                            {p.ministry}
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>

              {/* Debate Digest Callout */}
              <div className="bg-gradient-to-br from-stone-900 to-indigo-950 text-white rounded-2xl p-5 shadow-xs border border-stone-800">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-indigo-400 mb-2">
                  <FileText className="w-3.5 h-3.5" />
                  Parliament Hansard Hub
                </div>
                <h3 className="font-serif font-bold text-base text-white">
                  Singapore Parliament Debate Digest
                </h3>
                <p className="text-xs text-stone-300 mt-1.5 leading-relaxed">
                  Catch up on official ministerial statements, sitting transcripts, and automated debate summaries from recent sessions.
                </p>
                <div className="mt-4">
                  <Link
                    to="/debates"
                    className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
                  >
                    <span>Explore Hansard Sittings</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>

              {/* Open Policy Query Banner */}
              <div className="bg-stone-50 border border-stone-200/90 rounded-2xl p-5 shadow-xs">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-700 mb-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  Custom Policy Query
                </div>
                <h4 className="text-xs font-semibold text-stone-900">
                  Have a specific question not covered here?
                </h4>
                <p className="text-[11px] text-stone-500 mt-1 leading-normal">
                  Our live Policy Query Agent can search across all official Singapore government portals (`.gov.sg`) in real time.
                </p>
                <div className="mt-3">
                  <Link
                    to="/query"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
                  >
                    <span>Launch Open Policy Assistant</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </aside>
          </div>
        </section>
      )}
    </div>
  );
}
