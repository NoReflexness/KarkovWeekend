import { describe, expect, it } from "vitest";
import { ageOn, classifyAge, categoryLabel } from "./age";

const rules = { baby_max_age: 2, kid_max_age: 13 };

describe("ageOn", () => {
  it("computes age before birthday correctly", () => {
    const on = new Date("2026-05-09");
    expect(ageOn("2020-12-01", on)).toBe(5);
  });
  it("returns null for missing birthdate", () => {
    expect(ageOn(null)).toBeNull();
  });
});

describe("classifyAge", () => {
  it("classifies a baby", () => {
    expect(classifyAge(1, rules)).toBe("baby");
  });
  it("classifies a kid at the boundary", () => {
    expect(classifyAge(13, rules)).toBe("kid");
  });
  it("classifies a teen above the cutoff", () => {
    expect(classifyAge(14, rules)).toBe("teen_adult");
  });
  it("falls back to unknown without rules", () => {
    expect(classifyAge(5, undefined)).toBe("unknown");
  });
});

describe("categoryLabel", () => {
  it("returns Danish labels", () => {
    expect(categoryLabel("baby")).toBe("Baby");
    expect(categoryLabel("kid")).toBe("Barn");
    expect(categoryLabel("teen_adult")).toBe("Teenager");
  });
});
