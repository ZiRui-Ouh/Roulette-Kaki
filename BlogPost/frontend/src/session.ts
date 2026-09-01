import type { ChatMessage } from "./types";

export interface StoredSession {
  session_id: string;
  topic_ids: string[];
  messages: ChatMessage[];
}

const key = (date: string) => `chat:${date}`;

export function loadSession(date: string): StoredSession | null {
  try {
    const raw = localStorage.getItem(key(date));
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function saveSession(date: string, session: StoredSession): void {
  try {
    localStorage.setItem(key(date), JSON.stringify(session));
  } catch {
    // Storage disabled or full — ignore.
  }
}

export function clearSession(date: string): void {
  localStorage.removeItem(key(date));
}
