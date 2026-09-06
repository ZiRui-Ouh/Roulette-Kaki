import { useCallback, useEffect, useRef, useState } from "react";
import {
  X,
  Layers,
  RefreshCw,
  Save,
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Check,
  Sparkles,
} from "lucide-react";
import {
  generateChatFlashcards,
  generateTopicFlashcards,
} from "../api";
import {
  deleteDeck as deleteDeckStorage,
  loadSavedDecks,
  saveDeck as saveDeckStorage,
} from "../session";
import { useLanguage } from "../contexts/LanguageContext";
import type { FlashcardDeck, SavedDeck } from "../types";

export type DrawerSource =
  | { kind: "topic"; topicId: string; topicTitle: string }
  | { kind: "chat"; replyText: string; topicIds?: string[] };

interface Props {
  open: boolean;
  date: string;
  source: DrawerSource | null;
  onClose: () => void;
}

export default function FlashcardDrawer({
  open,
  date,
  source,
  onClose,
}: Props) {
  const { language } = useLanguage();
  const panelRef = useRef<HTMLDivElement>(null);
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState<FlashcardDeck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedDeck[]>([]);
  const [justSavedAt, setJustSavedAt] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  // Bump to force a fresh generation for the same (source, date). Used by
  // the "Regenerate" button.
  const [regenNonce, setRegenNonce] = useState(0);

  // Refresh saved decks whenever the drawer opens or the date/language changes.
  useEffect(() => {
    if (!open) return;
    setSaved(loadSavedDecks(date, language));
  }, [open, date, language]);

  // Fire generation whenever the drawer opens with a source (or Regenerate
  // is clicked). Resets stale preview/error/justSaved in the same tick so
  // the UI doesn't flash old state.
  //
  // NB: `preview` and `generating` are intentionally NOT in the deps —
  // including them causes the effect to re-run on its own state writes,
  // which cancels the in-flight fetch and leaves the spinner stuck.
  useEffect(() => {
    if (!open || !source) return;
    let cancelled = false;
    setPreview(null);
    setError(null);
    setJustSavedAt(null);
    setGenerating(true);

    const req =
      source.kind === "topic"
        ? generateTopicFlashcards(date, source.topicId)
        : generateChatFlashcards(date, source.replyText, source.topicIds);

    req
      .then((deck) => {
        if (cancelled) return;
        setPreview(deck);
      })
      .catch((e: { message?: string; error?: string }) => {
        if (cancelled) return;
        setError(e?.message || e?.error || "Failed to generate flashcards.");
      })
      .finally(() => {
        if (cancelled) return;
        setGenerating(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, source, date, regenNonce]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Close on outside click of the panel.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open, onClose]);

  const handleSave = useCallback(() => {
    if (!preview || !preview.cards.length) return;
    const savedAt = Date.now();
    const topicTitle =
      source?.kind === "topic" ? source.topicTitle : undefined;
    const record: SavedDeck = { ...preview, savedAt, topicTitle };
    const next = saveDeckStorage(date, record, language);
    setSaved(next);
    setJustSavedAt(savedAt);
  }, [preview, source, date, language]);

  const handleRegenerate = useCallback(() => {
    if (!source) return;
    setRegenNonce((n) => n + 1);
  }, [source]);

  const handleDelete = useCallback(
    (savedAt: number) => {
      const next = deleteDeckStorage(date, savedAt, language);
      setSaved(next);
      setExpanded((prev) => {
        const copy = new Set(prev);
        copy.delete(savedAt);
        return copy;
      });
    },
    [date, language],
  );

  const toggleExpanded = useCallback((savedAt: number) => {
    setExpanded((prev) => {
      const copy = new Set(prev);
      if (copy.has(savedAt)) copy.delete(savedAt);
      else copy.add(savedAt);
      return copy;
    });
  }, []);

  const sourceLabel =
    source?.kind === "topic"
      ? source.topicTitle
      : source?.kind === "chat"
        ? "Research assistant reply"
        : "Flashcards";

  return (
    <div
      className={`fixed inset-0 z-40 transition-opacity duration-200 ${
        open ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
      aria-hidden={!open}
    >
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <aside
        ref={panelRef}
        role="dialog"
        aria-label="Flashcards drawer"
        className={`absolute right-0 top-0 h-full w-full sm:max-w-md bg-white shadow-2xl border-l border-stone-200 flex flex-col transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-stone-200 bg-stone-50/80">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-stone-500">
              <Sparkles className="w-3 h-3 text-indigo-500" />
              Flashcards
            </div>
            <h2 className="font-serif font-bold text-stone-900 text-sm leading-snug mt-0.5 truncate">
              {sourceLabel}
            </h2>
            <div className="text-[10px] text-stone-500 mt-0.5">
              Sitting of {date}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-stone-400 hover:text-stone-900 p-1 rounded-lg hover:bg-stone-100 transition cursor-pointer"
            aria-label="Close flashcards drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scroll body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Preview section — only rendered when a source is active. */}
          {source && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-stone-500">
                  <Layers className="w-3.5 h-3.5" />
                  New deck
                </div>
                {preview && !error && (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleRegenerate}
                      disabled={generating}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-600 hover:text-stone-900 px-2 py-1 rounded-md hover:bg-stone-100 transition disabled:opacity-40 cursor-pointer"
                      title="Regenerate this deck"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Regenerate
                    </button>
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={justSavedAt !== null || preview.cards.length === 0}
                      className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-md transition cursor-pointer ${
                        justSavedAt !== null
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-stone-900 text-white hover:bg-stone-800"
                      }`}
                    >
                      {justSavedAt !== null ? (
                        <>
                          <Check className="w-3 h-3" />
                          Saved
                        </>
                      ) : (
                        <>
                          <Save className="w-3 h-3" />
                          Save deck
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>

              {generating && (
                <div className="flex items-center gap-2 text-xs text-stone-500 italic p-3 bg-stone-50 rounded-xl border border-stone-100">
                  <div className="w-2 h-2 rounded-full bg-stone-600 animate-pulse" />
                  <span>Distilling flashcards from source…</span>
                </div>
              )}

              {error && !generating && (
                <div className="text-xs bg-red-50 border border-red-200 text-red-900 rounded-xl p-3 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Could not generate.</div>
                    <div className="mt-0.5">{error}</div>
                    <button
                      type="button"
                      onClick={handleRegenerate}
                      className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-red-800 hover:text-red-900 underline cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Try again
                    </button>
                  </div>
                </div>
              )}

              {!generating && !error && preview && (
                <>
                  {preview.cards.length === 0 ? (
                    <div className="text-xs text-stone-500 italic p-3 bg-stone-50 rounded-xl border border-stone-100">
                      The model returned no cards. Try regenerating.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {preview.cards.map((c, idx) => (
                        <FlashcardTile key={c.id} index={idx + 1} title={c.title} body={c.body} />
                      ))}
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          {/* Saved decks section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-stone-500">
                <Save className="w-3.5 h-3.5" />
                Saved decks for this sitting
                <span className="text-stone-400">({saved.length})</span>
              </div>
            </div>

            {saved.length === 0 && (
              <div className="text-xs text-stone-500 italic p-3 bg-stone-50 rounded-xl border border-stone-100">
                Nothing saved yet. Generate a deck above and hit Save.
              </div>
            )}

            <div className="space-y-2">
              {saved.map((d) => {
                const isOpen = expanded.has(d.savedAt);
                const header =
                  d.topicTitle ||
                  (d.source === "chat"
                    ? "Research assistant reply"
                    : d.topic_id || "Untitled deck");
                return (
                  <div
                    key={d.savedAt}
                    className="rounded-xl border border-stone-200 bg-white shadow-xs overflow-hidden"
                  >
                    <div className="flex items-center justify-between gap-2 px-3 py-2.5">
                      <button
                        type="button"
                        onClick={() => toggleExpanded(d.savedAt)}
                        className="flex-1 flex items-center gap-2 text-left cursor-pointer"
                      >
                        {isOpen ? (
                          <ChevronUp className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-stone-900 truncate">
                            {header}
                          </div>
                          <div className="text-[10px] text-stone-500 mt-0.5">
                            {d.cards.length} card{d.cards.length === 1 ? "" : "s"} ·{" "}
                            <span className="uppercase font-mono">{d.source}</span>
                          </div>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(d.savedAt)}
                        className="shrink-0 text-stone-400 hover:text-red-600 p-1.5 rounded-md hover:bg-red-50 transition cursor-pointer"
                        aria-label="Delete deck"
                        title="Delete deck"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    {isOpen && (
                      <div className="px-3 pb-3 space-y-2 bg-stone-50/50 border-t border-stone-100">
                        {d.cards.map((c, idx) => (
                          <FlashcardTile
                            key={c.id}
                            index={idx + 1}
                            title={c.title}
                            body={c.body}
                            compact
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

function FlashcardTile({
  index,
  title,
  body,
  compact = false,
}: {
  index: number;
  title: string;
  body: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50/40 via-white to-white shadow-xs ${
        compact ? "p-3" : "p-5"
      }`}
    >
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-amber-700 mb-1">
        <span className="w-4 h-4 rounded-full bg-amber-100 border border-amber-200 flex items-center justify-center text-[9px] text-amber-800">
          {index}
        </span>
        Card
      </div>
      <div
        className={`font-serif font-bold text-stone-900 leading-snug ${
          compact ? "text-sm" : "text-sm sm:text-base mb-1.5"
        }`}
      >
        {title}
      </div>
      <div
        className={`text-stone-600 leading-relaxed font-sans ${
          compact ? "text-[11px] mt-1" : "text-xs"
        }`}
      >
        {body}
      </div>
    </div>
  );
}
