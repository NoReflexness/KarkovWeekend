"use client";

import { useMemo } from "react";
import { Users } from "lucide-react";

import { da } from "@/i18n/da";
import type { AttendeeSummary, KarkovEvent } from "@/lib/types";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? "?";
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function AttendeesSummary({ event }: { event: KarkovEvent }) {
  const totalDays = event.days.length;
  const rawAttendees = event.attendees;

  const { attendees, groups } = useMemo(() => {
    const list = rawAttendees ?? [];
    const m = new Map<string, { label: string; members: AttendeeSummary[] }>();
    for (const a of list) {
      const key = a.family_id ? `f:${a.family_id}` : "f:none";
      const label = a.family_name ?? "Uden familie";
      if (!m.has(key)) m.set(key, { label, members: [] });
      m.get(key)!.members.push(a);
    }
    // Within each group: adults first, then children, both alpha-sorted.
    for (const g of m.values()) {
      g.members.sort((x, y) => {
        const xc = x.role === "child" ? 1 : 0;
        const yc = y.role === "child" ? 1 : 0;
        if (xc !== yc) return xc - yc;
        return x.name.localeCompare(y.name);
      });
    }
    const sorted = Array.from(m.values()).sort((a, b) =>
      a.label.localeCompare(b.label),
    );
    return { attendees: list, groups: sorted };
  }, [rawAttendees]);

  return (
    <div className="bg-background/30 ring-foreground/5 mt-4 rounded-lg p-3 ring-1">
      <div className="text-muted-foreground mb-2 flex items-center gap-2 text-xs uppercase tracking-wide">
        <Users className="size-4" />
        <span className="font-medium">{da.events.attendees}</span>
        <span>·</span>
        <span>
          {attendees.length === 0
            ? da.events.attendeesNone
            : da.events.attendeesCount(attendees.length)}
        </span>
      </div>
      {attendees.length === 0 ? null : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g) => (
            <div key={g.label} className="grid gap-1">
              <p className="text-muted-foreground text-xs">{g.label}</p>
              <div className="flex flex-wrap items-center gap-2">
                {g.members.map((m) => (
                  <span
                    key={m.user_id}
                    className="bg-card/70 ring-foreground/10 inline-flex items-center gap-1.5 rounded-full py-0.5 pl-0.5 pr-2 text-sm ring-1"
                    title={da.events.daysAttendedShort(m.days_attended, totalDays)}
                  >
                    <Avatar className="size-6">
                      {m.profile_picture_url && (
                        <AvatarImage src={m.profile_picture_url} alt={m.name} />
                      )}
                      <AvatarFallback className="text-[10px]">
                        {initials(m.name)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="truncate max-w-[10rem]">{m.name}</span>
                    {m.days_attended < totalDays && (
                      <Badge variant="outline" className="text-[10px] py-0 px-1">
                        {m.days_attended}/{totalDays}
                      </Badge>
                    )}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
