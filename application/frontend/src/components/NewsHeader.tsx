import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Flame,
  Search,
  MessageSquareText,
  Clock,
  SlidersHorizontal,
  Landmark,
  Layers,
} from "lucide-react";
import { CATEGORIES } from "../data/policies";
import type { PolicyCategory } from "../types";
import LanguageSwitcher from "./LanguageSwitcher";

interface NewsHeaderProps {
  selectedCategory?: PolicyCategory | "All";
  onSelectCategory?: (category: PolicyCategory | "All") => void;
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
}

// Provides global navigation, policy filtering, search, and language controls.
export default function NewsHeader({
  selectedCategory = "All",
  onSelectCategory,
  searchQuery = "",
  onSearchChange,
}: NewsHeaderProps) {
  const location = useLocation();
  const [currentDateStr, setCurrentDateStr] = useState("");
  const isPolicies =
    location.pathname.startsWith("/policies") ||
    location.pathname.startsWith("/policy");
  const isDebates =
    location.pathname === "/" || location.pathname.startsWith("/debates");
  const isOpenQuery = location.pathname.startsWith("/query");

  useEffect(() => {
    const d = new Date();
    const formatted = d.toLocaleDateString("en-SG", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    setCurrentDateStr(formatted);
  }, []);

  const breakingAlerts = [
    "HDB BTO: Singles eligible for 2-room Flexi in Standard, Plus, & Prime projects islandwide",
    "CPF Board: Special Account closes at age 55; Enhanced Retirement Sum raised to 4x BRS",
    "MOH: MediShield Life policy year claim cap increased to $200,000",
    "MSF: Government-paid Shared Parental Leave increases to 10 weeks by April 2026",
    "SSG: $4,000 SkillsFuture Credit top-up & up to $3,000/mo training allowance active",
  ];

  const [alertIndex, setAlertIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setAlertIndex((prev) => (prev + 1) % breakingAlerts.length);
    }, 4500);
    return () => clearInterval(timer);
  }, [breakingAlerts.length]);

  return (
    <header className="bg-white border-b border-stone-200/90 shadow-xs">
      {/* Top utility bar: Date & Live Alerts */}
      <div className="bg-stone-900 text-stone-300 text-xs border-b border-stone-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-3 text-xs tracking-wide text-stone-400">
            <span className="flex items-center gap-1.5">
              <Clock className="w-5 h-5 text-stone-500" />
              {currentDateStr || "Singapore Edition"}
            </span>
            <span className="text-stone-700">|</span>
            <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Policy Intelligence
            </span>
          </div>

          <div className="flex items-center gap-3 overflow-hidden max-w-full sm:max-w-2xl text-xs">
            <div className="flex items-center gap-2 overflow-hidden min-w-0">
              <span className="bg-red-600 text-white font-bold uppercase tracking-wider px-2 py-0.5 rounded text-[10px] flex items-center gap-1 shrink-0">
                <Flame className="w-5 h-5" />
                Gazette Alert
              </span>
              <div className="truncate text-stone-300 transition-all duration-300">
                {breakingAlerts[alertIndex]}
              </div>
            </div>
            <span className="text-stone-700 hidden sm:inline">|</span>
            <LanguageSwitcher />
          </div>
        </div>
      </div>

      {/* Newspaper Masthead */}
      <div className="max-w-7xl mx-auto px-5 sm:px-6 py-8 sm:py-11 border-b border-stone-200">
        <div className="flex flex-col md:flex-row items-center justify-between gap-5 text-center md:text-left">
          <div>
            <div className="text-xs sm:text-sm font-semibold uppercase tracking-[0.25em] text-stone-500 mb-2">
              The Independent Singapore Policy & Legislative Intelligence
            </div>
            <Link to="/" className="inline-block group">
              <h1 className="font-serif text-4xl sm:text-5xl md:text-6xl font-black tracking-tight text-stone-900 group-hover:text-indigo-900 transition font-black">
                THE SINGAPORE CHRONICLES
              </h1>
            </Link>
            <p className="text-sm text-stone-500 mt-2 font-sans">
              Official Gazette Dispatches &bull; Real-time AI Query Agent &bull; Sourced from Singapore Government Open Data
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 flex-wrap justify-center md:justify-end">
            <Link
              to="/"
              className={`inline-flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-sm font-semibold transition border ${
                isDebates
                  ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                  : "bg-white text-stone-700 border-stone-300 hover:bg-stone-50 hover:text-stone-900"
              }`}
            >
              <Landmark className={`w-4 h-4 ${isDebates ? "text-white" : "text-indigo-600"}`} />
              <span>Parliament Debates</span>
            </Link>

            <Link
              to="/policies"
              className={`inline-flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-sm font-semibold transition border ${
                isPolicies
                  ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                  : "bg-white text-stone-700 border-stone-300 hover:bg-stone-50 hover:text-stone-900"
              }`}
            >
              <Layers className={`w-4 h-4 ${isPolicies ? "text-white" : "text-indigo-600"}`} />
              <span>Policy Feed</span>
            </Link>

            <Link
              to="/query"
              className={`inline-flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-sm font-semibold transition border ${
                isOpenQuery
                  ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                  : "bg-white text-stone-700 border-stone-300 hover:bg-stone-50 hover:text-stone-900"
              }`}
            >
              <MessageSquareText className={`w-4 h-4 ${isOpenQuery ? "text-white" : "text-indigo-600"}`} />
              <span>Ask Query Agent</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Editorial Navigation & Categories Bar */}
      {isPolicies && (
        <div className="bg-stone-50/90 border-b border-stone-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 py-3">
            <nav className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none">
              <span className="text-xs font-bold uppercase tracking-wider text-stone-400 mr-2 shrink-0 flex items-center gap-1.5">
                <SlidersHorizontal className="w-5 h-5" />
                Desks:
              </span>
              {CATEGORIES.map((cat) => {
                const isActive = selectedCategory === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => onSelectCategory && onSelectCategory(cat.id)}
                    className={`whitespace-nowrap px-5 py-3 rounded-md text-sm font-medium transition cursor-pointer ${
                      isActive
                        ? "bg-stone-900 text-white shadow-xs font-semibold"
                        : "text-stone-600 hover:text-stone-900 hover:bg-stone-200/60"
                    }`}
                  >
                    {cat.label}
                  </button>
                );
              })}
            </nav>

            {/* Quick search input */}
            {onSearchChange && (
              <div className="relative shrink-0 sm:w-72">
                <Search className="w-5 h-5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search policies, keywords..."
                  value={searchQuery}
                  onChange={(e) => onSearchChange(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-sm rounded-md bg-white border border-stone-300 text-stone-800 placeholder-stone-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition"
                />
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
