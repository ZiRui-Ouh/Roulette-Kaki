import type { ReactNode } from "react";

// Split a raw query into normalised lowercase tokens. Whitespace splits,
// so "housing bto" and "bto housing" behave identically downstream.
export function tokenize(query: string): string[] {
  return query
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

// Every token must appear as a substring somewhere in the pool of fields
// (title, speaker names, …). AND-semantics — this is what makes multi-word
// queries feel intuitive instead of requiring an exact adjacent phrase.
export function matchesAllTokens(tokens: string[], fields: string[]): boolean {
  if (!tokens.length) return true;
  const haystack = fields.filter(Boolean).join(" ").toLowerCase();
  return tokens.every((tok) => haystack.includes(tok));
}

// Highlighting was intentionally removed — returns plain text so the
// filter behaves the same but no visual marker is painted per keystroke.
// This also drops the per-item regex/split/mark work that made typing
// feel sluggish on large lists.
export function highlightMatches(text: string, _tokens: string[]): ReactNode {
  return text;
}
