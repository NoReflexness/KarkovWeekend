import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { formatKr, daysUntil, mapsEmbedUrl, mapsOpenUrl } from "./format";

describe("formatKr", () => {
  it("formats integer cents", () => {
    expect(formatKr(1234)).toMatch(/12,34/);
  });
  it("formats with thousand separators", () => {
    expect(formatKr(123456)).toMatch(/1\.234,56/);
  });
});

function localDateString(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

describe("daysUntil", () => {
  it("returns 0 for today", () => {
    expect(daysUntil(localDateString(0))).toBe(0);
  });
  it("returns positive for the future", () => {
    expect(daysUntil(localDateString(5))).toBe(5);
  });
  it("returns negative for the past", () => {
    expect(daysUntil(localDateString(-3))).toBe(-3);
  });
});

describe("mapsEmbedUrl / mapsOpenUrl", () => {
  const KEY_ENV = "NEXT_PUBLIC_GOOGLE_MAPS_API_KEY";
  const original = process.env[KEY_ENV];

  beforeEach(() => {
    delete process.env[KEY_ENV];
  });
  afterEach(() => {
    if (original === undefined) delete process.env[KEY_ENV];
    else process.env[KEY_ENV] = original;
  });

  it("returns null for empty input", () => {
    expect(mapsEmbedUrl(null)).toBeNull();
    expect(mapsEmbedUrl("   ")).toBeNull();
    expect(mapsOpenUrl(undefined)).toBeNull();
  });

  it("uses keyless embed when no API key is configured", () => {
    const u = mapsEmbedUrl("Karkov, Danmark")!;
    expect(u).toContain("https://www.google.com/maps?q=");
    expect(u).toContain("output=embed");
    expect(u).not.toContain("/embed/v1/");
  });

  it("uses Maps Embed API when key is configured", () => {
    process.env[KEY_ENV] = "TEST-KEY";
    const u = mapsEmbedUrl("Karkov, Danmark")!;
    expect(u).toContain("https://www.google.com/maps/embed/v1/place");
    expect(u).toContain("key=TEST-KEY");
    expect(u).toContain("q=Karkov");
  });

  it("encodes the open-in-maps query", () => {
    const u = mapsOpenUrl("Hovedgaden 1, 6000 Kolding")!;
    expect(u).toContain("https://www.google.com/maps/search/?api=1");
    expect(u).toContain("query=Hovedgaden");
  });
});
