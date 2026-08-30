import type {
  ApiError,
  ChatResponse,
  DebateSummary,
  Digest,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
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

export function listDebates(): Promise<{ debates: DebateSummary[] }> {
  return request("/debates");
}

export function getDigest(date: string): Promise<Digest> {
  return request(`/debates/${encodeURIComponent(date)}`);
}

export function sendChat(
  date: string,
  body: { session_id?: string; message: string; topic_id?: string }
): Promise<ChatResponse> {
  return request(`/debates/${encodeURIComponent(date)}/chat`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
