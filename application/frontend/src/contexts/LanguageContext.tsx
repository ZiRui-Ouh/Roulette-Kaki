import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Lang } from "../types";

const STORAGE_KEY = "roulette-kaki:lang";
const DEFAULT_LANG: Lang = "English";

interface LanguageContextValue {
  language: Lang;
  setLanguage: (lang: Lang) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

// The selected language starts from browser storage, then is shared with all
// pages and saved again whenever the user changes it.
function readStored(): Lang {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (
      raw === "English" ||
      raw === "Chinese" ||
      raw === "Malay" ||
      raw === "Tamil" ||
      raw === "Singlish"
    ) {
      return raw;
    }
  } catch {
    // localStorage disabled — fall through to default.
  }
  return DEFAULT_LANG;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Lang>(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // Storage disabled or full — ignore.
    }
  }, [language]);

  const setLanguage = useCallback((lang: Lang) => {
    setLanguageState(lang);
  }, []);

  const value = useMemo(() => ({ language, setLanguage }), [language, setLanguage]);

  return (
    // Pages access the same language through useLanguage().
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used inside <LanguageProvider>");
  }
  return ctx;
}
