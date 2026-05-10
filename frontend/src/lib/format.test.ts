import { describe, expect, it } from "vitest";
import { formatKr, daysUntil } from "./format";

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
