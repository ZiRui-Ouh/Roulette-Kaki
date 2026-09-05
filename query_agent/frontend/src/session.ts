import type { ChatMessage, Lang, SavedDeck } from "./types";

export interface StoredSession {
  session_id: string;
  topic_ids: string[];
  messages: ChatMessage[];
}

// Chat histories are bucketed per language so a mid-conversation
// language flip doesn't mix scripts inside the same thread. Existing
// pre-i18n keys (`chat:{date}`, `query_agent:messages`) are the same as
// the new English-bucket keys so users don't lose their history.
const debateKey = (date: string, language: Lang) =>
  language === "English" ? `chat:${date}` : `chat:${date}:${language}`;
const queryChatKey = (language: Lang) =>
  language === "English" ? "query_agent:messages" : `query_agent:messages:${language}`;

export function loadDebateSession(
  date: string,
  language: Lang = "English",
): StoredSession | null {
  try {
    const raw = localStorage.getItem(debateKey(date, language));
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function saveDebateSession(
  date: string,
  session: StoredSession,
  language: Lang = "English",
): void {
  try {
    localStorage.setItem(debateKey(date, language), JSON.stringify(session));
  } catch {
    // Storage disabled or full — ignore.
  }
}

export function clearDebateSession(
  date: string,
  language: Lang = "English",
): void {
  localStorage.removeItem(debateKey(date, language));
}

export function loadQueryMessages(language: Lang = "English"): ChatMessage[] {
  try {
    const raw = localStorage.getItem(queryChatKey(language));
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

export function saveQueryMessages(
  messages: ChatMessage[],
  language: Lang = "English",
): void {
  try {
    localStorage.setItem(queryChatKey(language), JSON.stringify(messages));
  } catch {
    // Storage disabled or full — ignore.
  }
}

export function clearQueryMessages(language: Lang = "English"): void {
  localStorage.removeItem(queryChatKey(language));
}

// Flashcards saved per sitting per language, mirroring the chat bucket
// convention so a language flip doesn't mix scripts inside one deck list.
const flashcardsKey = (date: string, language: Lang) =>
  language === "English"
    ? `flashcards:${date}`
    : `flashcards:${date}:${language}`;

export function loadSavedDecks(
  date: string,
  language: Lang = "English",
): SavedDeck[] {
  try {
    const raw = localStorage.getItem(flashcardsKey(date, language));
    return raw ? (JSON.parse(raw) as SavedDeck[]) : [];
  } catch {
    return [];
  }
}

export function saveDeck(
  date: string,
  deck: SavedDeck,
  language: Lang = "English",
): SavedDeck[] {
  const current = loadSavedDecks(date, language);
  const cardKey = deck.cards.map((c) => c.id).join("|");
  const existing = current.some(
    (d) => d.cards.map((c) => c.id).join("|") === cardKey,
  );
  const next = existing ? current : [deck, ...current];
  try {
    localStorage.setItem(flashcardsKey(date, language), JSON.stringify(next));
  } catch {
    // Storage disabled or full — ignore.
  }
  return next;
}

export function deleteDeck(
  date: string,
  savedAt: number,
  language: Lang = "English",
): SavedDeck[] {
  const next = loadSavedDecks(date, language).filter(
    (d) => d.savedAt !== savedAt,
  );
  try {
    localStorage.setItem(flashcardsKey(date, language), JSON.stringify(next));
  } catch {
    // Storage disabled or full — ignore.
  }
  return next;
}

export function clearSavedDecks(
  date: string,
  language: Lang = "English",
): void {
  localStorage.removeItem(flashcardsKey(date, language));
}
