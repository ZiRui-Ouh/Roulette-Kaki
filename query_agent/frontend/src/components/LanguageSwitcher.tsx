import { Languages } from "lucide-react";
import { useLanguage } from "../contexts/LanguageContext";
import { LANGUAGES, type Lang } from "../types";

export default function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage();

  return (
    <label className="flex items-center gap-1.5 text-[11px] tracking-wide text-stone-300 cursor-pointer">
      <Languages className="w-3 h-3 text-stone-500" />
      <span className="sr-only">Language</span>
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as Lang)}
        className="bg-stone-800 text-stone-200 border border-stone-700 rounded px-1.5 py-0.5 text-[11px] focus:outline-hidden focus:ring-1 focus:ring-emerald-500 cursor-pointer"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  );
}
