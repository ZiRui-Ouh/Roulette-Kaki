import type {
  ApiError,
  ChatResponse,
  DebateSummary,
  Digest,
  Sitting,
} from "./types";

const QUERY_API_BASE =
  import.meta.env.VITE_QUERY_API_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

const BLOGPOST_API_BASE =
  import.meta.env.VITE_BLOGPOST_API_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

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
}

/**
 * Query Agent API - send policy question to the backend with optional session memory
 */
export async function askQuery(
  question: string,
  sessionId?: string,
): Promise<QueryResponse> {
  const data = await request<QueryResponse>(QUERY_API_BASE, "/query", {
    method: "POST",
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  return data;
}

/**
 * Debate Digest & Sitting API endpoints
 */
export function listDebates(): Promise<{ debates: DebateSummary[] }> {
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

export function getDigest(date: string): Promise<Digest> {
  return request(BLOGPOST_API_BASE, `/debates/${encodeURIComponent(date)}`);
}

export function sendChat(
  date: string,
  body: { session_id?: string; message: string; topic_id?: string },
): Promise<ChatResponse> {
  return request(BLOGPOST_API_BASE, `/debates/${encodeURIComponent(date)}/chat`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
