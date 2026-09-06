import { Link } from "react-router-dom";
import {
  Sparkles,
  Landmark,
  ArrowUpRight,
} from "lucide-react";
import type { Policy } from "../types";

interface PolicyNewsCardProps {
  policy: Policy;
}

// Renders one searchable policy item in the local news feed.
export default function PolicyNewsCard({ policy }: PolicyNewsCardProps) {
  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case "Housing":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "CPF & Finance":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "Healthcare":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "Jobs & Skills":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Grants & Families":
        return "bg-purple-50 text-purple-700 border-purple-200";
      default:
        return "bg-stone-100 text-stone-700 border-stone-200";
    }
  };

  return (
    <article className="group bg-white border border-stone-200/90 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-stone-300 transition-all duration-200 flex flex-col justify-between">
      <div>
        {/* Category & Ministry badge */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${getCategoryColor(
              policy.category,
            )}`}
          >
            {policy.category}
          </span>
          <span className="text-[11px] text-stone-400 font-medium truncate">
            {policy.publishedAt}
          </span>
        </div>

        {/* Headline */}
        <Link to={`/policy/${policy.id}`} className="block group-hover:text-indigo-600 transition-colors">
          <h3 className="font-serif font-bold text-base sm:text-lg text-stone-900 leading-snug line-clamp-2">
            {policy.headline}
          </h3>
        </Link>

        {/* Summary Excerpt */}
        <p className="mt-2 text-xs sm:text-sm text-stone-600 leading-relaxed line-clamp-3">
          {policy.summary}
        </p>

        {/* Key Highlight Metric */}
        {policy.keyFacts && policy.keyFacts.length > 0 && (
          <div className="mt-3.5 pt-3 border-t border-stone-100 flex items-center justify-between text-xs">
            <span className="text-stone-500 text-[11px]">{policy.keyFacts[0].label}:</span>
            <span className="font-semibold text-stone-800 text-[11px] bg-stone-50 px-2 py-0.5 rounded border border-stone-200/60">
              {policy.keyFacts[0].value}
            </span>
          </div>
        )}
      </div>

      {/* Card Footer: Ministry & AI Action */}
      <div className="mt-4 pt-3.5 border-t border-stone-100 flex items-center justify-between text-xs">
        <span className="text-[11px] text-stone-500 flex items-center gap-1 truncate max-w-[170px]">
          <Landmark className="w-3 h-3 text-stone-400 shrink-0" />
          <span className="truncate">{policy.ministry}</span>
        </span>

        <Link
          to={`/policy/${policy.id}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-stone-700 hover:text-indigo-600 group-hover:text-indigo-600 transition"
        >
          <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
          <span>Consult AI</span>
          <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        </Link>
      </div>
    </article>
  );
}
