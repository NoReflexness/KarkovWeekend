"use client";

import { BedDouble } from "lucide-react";

import { da } from "@/i18n/da";
import type { BedDemand } from "@/lib/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Variant = "ok" | "full" | "over" | "unknown";

function variantOf(d: BedDemand): Variant {
  if (d.bed_count == null) return "unknown";
  if (d.peak === 0) return "ok";
  if (d.peak < d.bed_count) return "ok";
  if (d.peak === d.bed_count) return "full";
  return "over";
}

const STYLES: Record<
  Variant,
  { ring: string; bar: string; chip: string; icon: string }
> = {
  ok: {
    ring: "ring-emerald-300/40 dark:ring-emerald-400/30",
    bar: "bg-gradient-to-r from-emerald-400/80 to-emerald-300/80",
    chip: "bg-emerald-400/15 text-emerald-700 dark:text-emerald-300",
    icon: "text-emerald-600 dark:text-emerald-400",
  },
  full: {
    ring: "ring-amber-300/40 dark:ring-amber-400/30",
    bar: "bg-gradient-to-r from-amber-400/80 to-amber-300/80",
    chip: "bg-amber-400/15 text-amber-700 dark:text-amber-300",
    icon: "text-amber-600 dark:text-amber-400",
  },
  over: {
    ring: "ring-rose-300/40 dark:ring-rose-400/30",
    bar: "bg-gradient-to-r from-rose-500/85 to-rose-400/85",
    chip: "bg-rose-400/15 text-rose-700 dark:text-rose-300",
    icon: "text-rose-600 dark:text-rose-400",
  },
  unknown: {
    ring: "ring-foreground/10",
    bar: "bg-foreground/30",
    chip: "bg-foreground/10 text-muted-foreground",
    icon: "text-muted-foreground",
  },
};

export function BedDemandWidget({ demand }: { demand: BedDemand }) {
  const v = variantOf(demand);
  const style = STYLES[v];
  const bedCount = demand.bed_count ?? 0;
  const fillPct = bedCount > 0 ? Math.min(100, Math.round((demand.peak / bedCount) * 100)) : 0;
  const overshootPct = bedCount > 0 && demand.peak > bedCount
    ? Math.min(100, Math.round(((demand.peak - bedCount) / bedCount) * 100))
    : 0;

  let status: string;
  if (v === "unknown") status = da.events.beds.noBedCount;
  else if (v === "ok") status = demand.peak === 0 ? da.events.beds.pendingHint : da.events.beds.enough;
  else if (v === "full") status = da.events.beds.atCapacity;
  else status = da.events.beds.over(demand.peak - bedCount);

  return (
    <Card className={`ring-1 ${style.ring}`}>
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <BedDouble className={`size-4 ${style.icon}`} />
          {da.events.beds.title}
        </CardTitle>
        {demand.bed_count != null && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.chip}`}
          >
            {da.events.beds.usage(demand.peak, demand.bed_count)}
          </span>
        )}
      </CardHeader>
      <CardContent className="grid gap-2">
        <div className="bg-foreground/5 relative h-2.5 overflow-hidden rounded-full">
          <div
            className={`h-full ${style.bar} transition-[width] duration-500`}
            style={{ width: `${fillPct}%` }}
          />
          {overshootPct > 0 && (
            <div
              className="bg-rose-500/60 absolute right-0 top-0 h-full"
              style={{ width: `${overshootPct}%` }}
            />
          )}
        </div>
        <div className="text-muted-foreground flex flex-wrap items-center justify-between gap-2 text-xs">
          <span>{status}</span>
          {demand.peak_date && (
            <span>{da.events.beds.peakOn(demand.peak_date)}</span>
          )}
        </div>
        <p className="text-muted-foreground text-xs italic">
          {da.events.beds.babyExcluded}
        </p>
      </CardContent>
    </Card>
  );
}
