"use client";

import { use, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, MapPin, Crown, ListChecks, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDateRange } from "@/lib/format";
import type { KarkovEvent, User } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ActivitiesTab } from "./activities-tab";
import { AttendeesSummary } from "./attendees-summary";
import { BedDemandWidget } from "./bed-demand";
import { BudgetTab } from "./budget-tab";
import { ChorsTab } from "./chors-tab";
import { DaysTab } from "./days-tab";
import { EditEventDialog } from "./edit-event-dialog";
import { EventActions } from "./event-actions";
import { PlanNextYearButton } from "./plan-next-year";
import { SummerhouseHero } from "./summerhouse-hero";

export default function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const eventId = Number(id);
  const { user } = useAuth();
  const { data: event, isLoading } = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => api.get<KarkovEvent>(`/events/${eventId}`),
  });
  const isChild = user?.role === "child";

  const { data: users } = useQuery({
    queryKey: ["users", "for-event", eventId],
    queryFn: () => api.get<User[]>("/users"),
    enabled: !!event,
  });

  if (isLoading || !event) {
    return <Skeleton className="h-96 w-full" />;
  }

  const host = event.host_user_id
    ? users?.find((u) => u.id === event.host_user_id)
    : null;

  const mapQuery = event.address ?? event.location_url;
  const mapEmbed = mapQuery
    ? `https://www.google.com/maps?q=${encodeURIComponent(mapQuery)}&output=embed`
    : null;
  const mapOpenUrl =
    event.location_url ??
    (mapQuery
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery)}`
      : null);

  return (
    <EventDetailBody
      event={event}
      host={host ?? null}
      mapEmbed={mapEmbed}
      mapOpenUrl={mapOpenUrl}
      isChild={isChild}
    />
  );
}

function EventDetailBody({
  event,
  host,
  mapEmbed,
  mapOpenUrl,
  isChild,
}: {
  event: KarkovEvent;
  host: User | null;
  mapEmbed: string | null;
  mapOpenUrl: string | null;
  isChild: boolean;
}) {
  const [tab, setTab] = useState<string>("days");

  const unassignedChorsCount = useMemo(
    () =>
      event.days.reduce(
        (n, d) => n + d.chors.filter((c) => c.assignee_user_id == null).length,
        0,
      ),
    [event.days],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-6"
    >
      <Card>
        <CardHeader className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-start">
          <div className="min-w-0">
            <CardTitle className="text-2xl">{event.name}</CardTitle>
            <p className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
              <CalendarDays className="size-4 shrink-0" />
              {formatDateRange(event.start_date, event.end_date)}
            </p>
            {event.address && (
              <p className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
                <MapPin className="size-4 shrink-0" />
                <span className="truncate">{event.address}</span>
              </p>
            )}
            {host && (
              <p className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
                <Crown className="size-4 text-amber-500 shrink-0" />
                {da.events.host}:{" "}
                <span className="text-foreground font-medium truncate">{host.name}</span>
              </p>
            )}
            <button
              type="button"
              onClick={() => setTab("chors")}
              className="text-muted-foreground hover:text-foreground mt-1 flex items-center gap-2 text-sm transition-colors"
            >
              <ListChecks className="size-4 shrink-0" />
              {unassignedChorsCount > 0 ? (
                <span className="text-amber-600 dark:text-amber-400 font-medium">
                  {da.events.unassignedChorsSummary(unassignedChorsCount)}
                </span>
              ) : (
                <span>{da.events.unassignedChorsAllDone}</span>
              )}
            </button>
          </div>

          {mapEmbed && (
            <a
              href={mapOpenUrl ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              title={da.events.openMap}
              aria-label={da.events.openMap}
              className="ring-foreground/10 hover:ring-foreground/30 group relative block size-32 shrink-0 overflow-hidden rounded-md ring-1 transition-shadow sm:size-40"
            >
              <iframe
                title="Kort"
                src={mapEmbed}
                className="pointer-events-none size-full"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
              <div className="absolute inset-0 bg-black/0 transition-colors group-hover:bg-black/10" />
              <ExternalLink className="absolute right-1.5 top-1.5 size-4 text-white drop-shadow opacity-80 group-hover:opacity-100" />
            </a>
          )}

          <div className="flex flex-col items-stretch gap-2 sm:items-end">
            <Badge variant="secondary" className="self-end">
              {da.events.statusLabels[event.status]}
            </Badge>
            <EventActions event={event} />
            <div className="flex flex-wrap gap-2 sm:justify-end">
              <EditEventDialog event={event} />
              <PlanNextYearButton event={event} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <AttendeesSummary event={event} />
          {event.description && (
            <p className="mt-3 text-sm">{event.description}</p>
          )}
        </CardContent>
      </Card>

      <SummerhouseHero event={event} />

      <BedDemandWidget demand={event.bed_demand} />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="w-full justify-start overflow-auto">
          <TabsTrigger value="days">{da.events.days}</TabsTrigger>
          <TabsTrigger value="chors">{da.events.chors}</TabsTrigger>
          <TabsTrigger value="activities">{da.events.activities}</TabsTrigger>
          {!isChild && <TabsTrigger value="budget">{da.events.budget}</TabsTrigger>}
        </TabsList>
        <TabsContent value="days">
          <DaysTab event={event} />
        </TabsContent>
        <TabsContent value="chors">
          <ChorsTab event={event} />
        </TabsContent>
        <TabsContent value="activities">
          <ActivitiesTab event={event} />
        </TabsContent>
        {!isChild && (
          <TabsContent value="budget">
            <BudgetTab event={event} />
          </TabsContent>
        )}
      </Tabs>
    </motion.div>
  );
}
