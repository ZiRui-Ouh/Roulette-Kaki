import { Link } from "react-router-dom";
import {
  Sparkles,
  ArrowRight,
  Landmark,
  Calendar,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import type { Policy } from "../types";

interface PolicyHeroCardProps {
  policy: Policy;
}

export default function PolicyHeroCard({ policy }: PolicyHeroCardProps) {
  return (
    <article className="group relative bg-white border border-stone-200/90 rounded-2xl shadow-xs overflow-hidden hover:shadow-md transition-all duration-300">
      <div className="grid lg:grid-cols-12 gap-0">
        {/* Left / Top Editorial Content */}
        <div className="lg:col-span-8 p-6 sm:p-8 flex flex-col justify-between">
          <div>
            {/* Meta header */}
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="bg-red-50 text-red-700 border border-red-200 text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-red-600" />
                {policy.badge || "Lead Story"}
              </span>

              <span className="bg-stone-100 text-stone-700 text-[11px] font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <Landmark className="w-3 h-3 text-stone-500" />
                {policy.ministry}
              </span>

              <span className="text-stone-400 text-xs">&bull;</span>
              <span className="text-stone-500 text-xs flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {policy.effectiveDate}
              </span>
            </div>

            {/* Headline */}
            <Link to={`/policy/${policy.id}`} className="block">
              <h2 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-black text-stone-900 leading-tight group-hover:text-indigo-600 transition-colors">
                {policy.headline}
              </h2>
            </Link>

            {/* Sub-headline / Lead paragraph */}
            <p className="mt-3 text-stone-600 text-sm sm:text-base leading-relaxed line-clamp-3">
              {policy.leadParagraph}
            </p>

            {/* Key Policy Data Pills */}
            <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {policy.keyFacts.slice(0, 3).map((fact, idx) => (
                <div
                  key={idx}
                  className="bg-stone-50 border border-stone-200/70 p-2.5 rounded-xl text-left"
                >
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-stone-400 truncate">
                    {fact.label}
                  </div>
                  <div className="text-xs font-bold text-stone-800 mt-0.5 truncate">
                    {fact.value}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom Action bar */}
          <div className="mt-6 pt-5 border-t border-stone-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-stone-500">
              <span className="inline-flex items-center gap-1 text-emerald-600 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Official Govt Verification
              </span>
              <span>&bull;</span>
              <span>{policy.readTime}</span>
            </div>

            <Link
              to={`/policy/${policy.id}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-stone-900 text-white hover:bg-indigo-600 text-xs sm:text-sm font-semibold transition-all duration-200 shadow-xs group-hover:bg-indigo-600"
            >
              <Sparkles className="w-4 h-4 text-amber-300" />
              <span>Read & Consult Policy AI</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Right Feature Panel: AI Preview Callout */}
        <div className="lg:col-span-4 bg-gradient-to-br from-stone-900 via-indigo-950 to-slate-900 text-white p-6 sm:p-7 flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-stone-800">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-400 mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              Interactive Chat Replacement
            </div>
            <h3 className="font-serif font-bold text-lg text-white">
              Instant Policy Intelligence
            </h3>
            <p className="text-xs text-stone-300 mt-1.5 leading-relaxed">
              Skip dense PDF circulars. Click into this article to immediately ask our Policy Query Agent about your eligibility, figures, and rules.
            </p>

            <div className="mt-4 space-y-2">
              <div className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                Common Inquiries:
              </div>
              {policy.suggestedQuestions.slice(0, 3).map((q, idx) => (
                <Link
                  key={idx}
                  to={`/policy/${policy.id}`}
                  className="block text-xs bg-white/10 hover:bg-white/20 text-stone-200 hover:text-white p-2.5 rounded-lg border border-white/10 transition backdrop-blur-xs truncate"
                >
                  &ldquo;{q}&rdquo;
                </Link>
              ))}
            </div>
          </div>

          <div className="mt-5 text-[11px] text-stone-400 flex items-center justify-between">
            <span>Query Agent Ready</span>
            <span className="text-emerald-400 font-semibold">● Online</span>
          </div>
        </div>
      </div>
    </article>
  );
}
