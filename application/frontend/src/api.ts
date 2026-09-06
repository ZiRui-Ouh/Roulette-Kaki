import type {
  ApiError,
  ChatResponse,
  DebateSummary,
  Digest,
  FlashcardDeck,
  Lang,
  Sitting,
} from "./types";
import { cleanSpeakerTags } from "./lib/audioUtils";

const QUERY_API_BASE =
  import.meta.env.VITE_QUERY_API_URL ||
  import.meta.env.VITE_API_URL ||
  "/api";

const BLOGPOST_API_BASE =
  import.meta.env.VITE_BLOGPOST_API_URL ||
  import.meta.env.VITE_API_URL ||
  "/api";

// All frontend requests pass through this function. It adds JSON headers,
// converts failed HTTP responses into one consistent error shape, and returns
// the decoded JSON for the page or component that asked for it.
async function request<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const resp = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!resp.ok) {
    let detail: { error?: string; message?: string } = {};
    try {
      const body = await resp.json();
      detail = body.detail && typeof body.detail === "object" ? body.detail : body;
    } catch {
      // non-JSON body — leave detail empty
    }
    const err: ApiError = {
      status: resp.status,
      error: detail.error || "unknown",
      message: detail.message || resp.statusText,
    };
    throw err;
  }

  return resp.json();
}

export interface QueryResponse {
  answer: string;
  session_id: string;
  language?: Lang;
}

/**
 * Query Agent API — send a policy question to the backend with optional
 * session memory and an optional target language.
 *
 * When `language` is non-English the backend translates the question to
 * English (with a key-points summary), runs the agent, and translates the
 * response back — see services/translation_wrapper.py.
 */
export async function askQuery(
  question: string,
  language: Lang = "English",
  sessionId?: string,
): Promise<QueryResponse> {
  // The backend uses sessionId to remember earlier policy questions.
  return request<QueryResponse>(QUERY_API_BASE, "/query", {
    method: "POST",
    body: JSON.stringify({ question, language, session_id: sessionId }),
  });
}

export interface TranscribeResponse {
  text?: string;
  transcript?: string;
}

/**
 * Speech-to-Text API — sends audio to backend to transcribe via MERaLiON API.
 */
export async function transcribeAudio(
  audioBase64: string,
  mime: string = "audio/webm",
): Promise<string> {
  const res = await request<TranscribeResponse>(QUERY_API_BASE, "/transcribe", {
    method: "POST",
    body: JSON.stringify({ audio_b64: audioBase64, mime }),
  });
  const rawText = (res.text || res.transcript || "").trim();
  return cleanSpeakerTags(rawText);
}

/**
 * Debate Digest & Sitting API endpoints
 */
export function listDebates(): Promise<{ debates: DebateSummary[] }> {
  // Debate endpoints are kept separate from policy-query endpoints because
  // they use the sitting and digest workflow.
  return request(BLOGPOST_API_BASE, "/debates");
}

export function listSittings(
  limit = 5,
  offset = 0,
): Promise<{ sittings: Sitting[]; total: number; has_more: boolean }> {
  const qs = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request(BLOGPOST_API_BASE, `/sittings?${qs}`);
}

export function getDigest(
  date: string,
  language: Lang = "English",
): Promise<Digest> {
  const qs = language === "English" ? "" : `?language=${encodeURIComponent(language)}`;
  return request(BLOGPOST_API_BASE, `/debates/${encodeURIComponent(date)}${qs}`);
}

export function sendChat(
  date: string,
  body: {
    session_id?: string;
    message: string;
    topic_id?: string;
    language?: Lang;
  },
): Promise<ChatResponse> {
  return request(BLOGPOST_API_BASE, `/debates/${encodeURIComponent(date)}/chat`, {
    method: "POST",
    body: JSON.stringify({ language: "English", ...body }),
  });
}

/**
 * Flashcards agent — condenses either a Hansard topic transcript or a
 * research-agent assistant reply into a deck of single-sided summary
 * cards. Response is returned in-memory; persistence is client-side via
 * session.ts helpers.
 */
export function generateTopicFlashcards(
  date: string,
  topicId: string,
  count = 5,
): Promise<FlashcardDeck> {
  return request(
    BLOGPOST_API_BASE,
    `/debates/${encodeURIComponent(date)}/flashcards/topic/${encodeURIComponent(topicId)}`,
    {
      method: "POST",
      body: JSON.stringify({ count }),
    },
  );
}

export function generateChatFlashcards(
  date: string,
  replyText: string,
  topicIds?: string[],
  count = 5,
): Promise<FlashcardDeck> {
  return request(
    BLOGPOST_API_BASE,
    `/debates/${encodeURIComponent(date)}/flashcards/from-chat`,
    {
      method: "POST",
      body: JSON.stringify({
        reply_text: replyText,
        topic_ids: topicIds,
        count,
      }),
    },
  );
}
