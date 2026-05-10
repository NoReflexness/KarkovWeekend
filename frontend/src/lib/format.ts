export function formatKr(cents: number): string {
  return (cents / 100).toLocaleString("da-DK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatDateRange(start: string, end: string): string {
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  const optsEnd: Intl.DateTimeFormatOptions = {
    day: "numeric",
    month: "short",
    year: "numeric",
  };
  const s = new Date(start);
  const e = new Date(end);
  return `${s.toLocaleDateString("da-DK", opts)}–${e.toLocaleDateString("da-DK", optsEnd)}`;
}

export function formatDate(d: string | Date): string {
  return new Date(d).toLocaleDateString("da-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function daysUntil(d: string): number {
  // Treat YYYY-MM-DD as a local date so we don't drift across the UTC boundary.
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d);
  const target = m
    ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
    : new Date(d);
  const now = new Date();
  target.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  const diff = target.getTime() - now.getTime();
  return Math.round(diff / (1000 * 60 * 60 * 24));
}

export function publicUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  const base =
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/api\/v1$/, "") ??
    "http://localhost:8000";
  return `${base}${path}`;
}

/**
 * Build a Google Maps embed URL.
 *
 * If `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is set we use the official Maps Embed
 * API (no "for development purposes only" watermark, supports more parameters).
 * Otherwise we fall back to the keyless `?q=...&output=embed` form, which
 * works without an API key but is technically unsupported by Google.
 */
export function mapsEmbedUrl(query: string | null | undefined): string | null {
  if (!query) return null;
  const trimmed = query.trim();
  if (!trimmed) return null;
  const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const q = encodeURIComponent(trimmed);
  if (key) {
    return `https://www.google.com/maps/embed/v1/place?key=${encodeURIComponent(
      key,
    )}&q=${q}`;
  }
  return `https://www.google.com/maps?q=${q}&output=embed`;
}

/** External "open in Maps" link, with API key when available. */
export function mapsOpenUrl(query: string | null | undefined): string | null {
  if (!query) return null;
  const trimmed = query.trim();
  if (!trimmed) return null;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
    trimmed,
  )}`;
}
