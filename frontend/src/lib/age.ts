import type { PricingRules } from "@/lib/types";

export type AgeCategory = "baby" | "kid" | "teen_adult" | "unknown";

export function ageOn(birthdate: string | null | undefined, on: Date = new Date()): number | null {
  if (!birthdate) return null;
  const bd = new Date(birthdate);
  if (Number.isNaN(bd.getTime())) return null;
  let age = on.getFullYear() - bd.getFullYear();
  const m = on.getMonth() - bd.getMonth();
  if (m < 0 || (m === 0 && on.getDate() < bd.getDate())) age--;
  return age;
}

export function classifyAge(age: number | null, rules: PricingRules | undefined): AgeCategory {
  if (age === null || rules === undefined) return "unknown";
  if (age <= rules.baby_max_age) return "baby";
  if (age <= rules.kid_max_age) return "kid";
  return "teen_adult";
}

export function categoryLabel(cat: AgeCategory): string {
  switch (cat) {
    case "baby":
      return "Baby";
    case "kid":
      return "Barn";
    case "teen_adult":
      return "Teenager";
    default:
      return "—";
  }
}

const VARIANT: Record<AgeCategory, "secondary" | "default" | "outline"> = {
  baby: "default",
  kid: "secondary",
  teen_adult: "outline",
  unknown: "outline",
};

export function categoryVariant(cat: AgeCategory): "secondary" | "default" | "outline" {
  return VARIANT[cat];
}
