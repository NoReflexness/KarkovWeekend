"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BedDouble, CalendarDays, MapPin } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { daysUntil, formatDateRange, mapsEmbedUrl } from "@/lib/format";
import type { KarkovEvent } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

export default function HomePage() {
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["events", "next"],
    queryFn: async () => {
      try {
        return await api.get<KarkovEvent>("/events/next");
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return <p className="text-destructive">{da.common.error}</p>;
  }

  if (!data) {
    const isAdmin = user?.role === "admin";
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>{da.events.next}</EmptyTitle>
          <EmptyDescription>{da.events.none}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild>
            <Link href="/arrangementer">
              {isAdmin ? da.events.create : da.events.list}
            </Link>
          </Button>
        </EmptyContent>
      </Empty>
    );
  }

  const days = daysUntil(data.start_date);
  const mapEmbed = data.location_url
    ? mapsEmbedUrl(data.address ?? data.location_url)
    : null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-6"
    >
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-0">
          <div className="absolute -right-24 -top-24 size-72 rounded-full bg-sky-400/30 blur-3xl dark:bg-sky-500/20" />
          <div className="absolute -bottom-32 -left-16 size-72 rounded-full bg-fuchsia-400/20 blur-3xl dark:bg-fuchsia-500/15" />
        </div>
        <CardHeader className="relative flex flex-row items-start justify-between gap-4">
          <div>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">
              {da.events.next}
            </p>
            <CardTitle className="text-balance mt-1 text-3xl font-semibold leading-tight">
              {data.name}
            </CardTitle>
            <p className="text-muted-foreground mt-2 flex items-center gap-2 text-sm">
              <CalendarDays className="size-4" />
              {formatDateRange(data.start_date, data.end_date)}
            </p>
            {data.address && (
              <p className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
                <MapPin className="size-4" />
                {data.address}
              </p>
            )}
            {data.bed_demand.bed_count != null && (
              <p className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
                <BedDouble className="size-4" />
                {da.events.beds.usage(data.bed_demand.peak, data.bed_demand.bed_count)}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant="secondary">{da.events.statusLabels[data.status]}</Badge>
            <span className="from-primary to-primary/60 bg-gradient-to-br bg-clip-text text-3xl font-semibold tracking-tight text-transparent">
              {da.events.countdown(days)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="relative flex flex-col gap-4">
          {data.description && <p className="text-balance">{data.description}</p>}
          <Button asChild className="w-fit">
            <Link href={`/arrangementer/${data.id}`}>Se detaljer</Link>
          </Button>
        </CardContent>
      </Card>

      {mapEmbed && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Hvor er det?</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="aspect-video w-full overflow-hidden rounded-md border">
              <iframe
                title="Kort"
                src={mapEmbed}
                className="size-full"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
          </CardContent>
        </Card>
      )}
    </motion.section>
  );
}
