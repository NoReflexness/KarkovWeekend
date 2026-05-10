"use client";

import Image from "next/image";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { KarkovEvent } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function SummerhouseHero({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isHostOrAdmin = user?.role === "admin" || user?.id === event.host_user_id;

  const scrape = useMutation({
    mutationFn: () => api.post<KarkovEvent>(`/events/${event.id}/scrape-summerhouse`, {}),
    onSuccess: () => {
      toast.success(da.events.summerhouse.fetchedToast);
      qc.invalidateQueries({ queryKey: ["event", event.id] });
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? e.message : da.events.summerhouse.fetchFailedToast;
      toast.error(msg);
    },
  });

  if (!event.summerhouse_url && !event.summerhouse_title && !event.summerhouse_image_url) {
    if (!isHostOrAdmin) return null;
    return (
      <Card>
        <CardContent className="text-muted-foreground py-4 text-sm">
          {da.events.summerhouse.noUrl}
        </CardContent>
      </Card>
    );
  }

  const hasScrape = Boolean(
    event.summerhouse_title || event.summerhouse_summary || event.summerhouse_image_url,
  );

  return (
    <Card className="overflow-hidden">
      {event.summerhouse_image_url && (
        <div className="relative aspect-[16/7] w-full overflow-hidden">
          <Image
            src={event.summerhouse_image_url}
            alt={event.summerhouse_title ?? "Feriehus"}
            fill
            sizes="(min-width: 1024px) 768px, 100vw"
            className="object-cover"
            unoptimized
          />
          <div className="from-background/90 absolute inset-x-0 bottom-0 bg-gradient-to-t to-transparent p-4">
            {event.summerhouse_title && (
              <p className="text-xl font-semibold drop-shadow">
                {event.summerhouse_title}
              </p>
            )}
          </div>
        </div>
      )}
      <CardContent className="grid gap-3 py-4">
        {!event.summerhouse_image_url && event.summerhouse_title && (
          <p className="text-lg font-semibold">{event.summerhouse_title}</p>
        )}
        {event.summerhouse_summary && (
          <p className="text-sm leading-relaxed">{event.summerhouse_summary}</p>
        )}
        <div className="text-muted-foreground flex flex-wrap items-center justify-between gap-2 text-xs">
          {event.summerhouse_url ? (
            <Link
              href={event.summerhouse_url}
              target="_blank"
              className="text-primary inline-flex items-center gap-1 hover:underline"
            >
              <ExternalLink className="size-3" />
              {da.events.summerhouse.visit}
            </Link>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-3">
            {event.summerhouse_scraped_at && (
              <span>{da.events.summerhouse.scrapedAt(event.summerhouse_scraped_at)}</span>
            )}
            {isHostOrAdmin && event.summerhouse_url && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => scrape.mutate()}
                disabled={scrape.isPending}
              >
                {hasScrape ? (
                  <RefreshCw className={`size-4 ${scrape.isPending ? "animate-spin" : ""}`} />
                ) : (
                  <Sparkles className="size-4" />
                )}
                {hasScrape ? da.events.summerhouse.refreshAssets : da.events.summerhouse.fetchAssets}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
