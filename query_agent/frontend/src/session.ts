import type { ChatMessage } from "./types";

export interface StoredSession {
  session_id: string;
  topic_ids: string[];
  messages: ChatMessage[];
}

const debateKey = (date: string) => `chat:${date}`;
const queryChatKey = "query_agent:messages";

export function loadDebateSession(date: string): StoredSession | null {
  try {
    const raw = localStorage.getItem(debateKey(date));
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function saveDebateSession(date: string, session: StoredSession): void {
  try {
    localStorage.setItem(debateKey(date), JSON.stringify(session));
  } catch {
    // Storage disabled or full — ignore.
  }
}

export function clearDebateSession(date: string): void {
  localStorage.removeItem(debateKey(date));
}

export function loadQueryMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(queryChatKey);
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

export function saveQueryMessages(messages: ChatMessage[]): void {
  try {
    localStorage.setItem(queryChatKey, JSON.stringify(messages));
  } catch {
    // Storage disabled or full — ignore.
  }
}

export function clearQueryMessages(): void {
  localStorage.removeItem(queryChatKey);
}
