import { useEffect, useState, type ReactNode, type SyntheticEvent } from "react";

interface Props {
  videoId: string | null;
  alt: string;
  imgClassName?: string;
  // Called with the ready <img> element so callers can wrap it with
  // their own anchor / overlay chrome. Only invoked when a real
  // thumbnail is available; otherwise `fallback` is rendered instead.
  renderReady: (imgEl: ReactNode) => ReactNode;
  fallback: ReactNode;
}

// YouTube serves this exact 120x90 grey "video unavailable" placeholder
// (a 200 OK, not a 404) for any invalid or removed video ID. Detect it
// by natural dimensions so we can swap to our own fallback card.
const GHOST_MAX_WIDTH = 120;

// Loads a YouTube thumbnail and provides a fallback when no usable video exists.
export default function YoutubeThumbnail({
  videoId,
  alt,
  imgClassName,
  renderReady,
  fallback,
}: Props) {
  // "max" → try maxresdefault.jpg (real 404 for non-existent videos).
  // "hq"  → fell back to hqdefault.jpg (always 200; may be ghost).
  // "gone" → confirmed unavailable; render fallback.
  const [level, setLevel] = useState<"max" | "hq" | "gone">("max");

  // Reset when videoId changes so a new video gets a fresh try.
  useEffect(() => {
    setLevel("max");
  }, [videoId]);

  if (!videoId || level === "gone") return <>{fallback}</>;

  const src =
    level === "max"
      ? `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`
      : `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;

  const handleError = () => {
    setLevel(level === "max" ? "hq" : "gone");
  };

  const handleLoad = (e: SyntheticEvent<HTMLImageElement>) => {
    if (e.currentTarget.naturalWidth <= GHOST_MAX_WIDTH) {
      setLevel(level === "max" ? "hq" : "gone");
    }
  };

  const img = (
    <img
      src={src}
      alt={alt}
      className={imgClassName}
      onError={handleError}
      onLoad={handleLoad}
    />
  );

  return <>{renderReady(img)}</>;
}
