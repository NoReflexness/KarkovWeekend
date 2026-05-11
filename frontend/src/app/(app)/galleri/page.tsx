"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Pause,
  Play,
  Star,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { da } from "@/i18n/da";
import { formatDate, publicUrl } from "@/lib/format";
import type { GalleryPhoto } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 200;

export default function GalleryPage() {
  const [dias, setDias] = useState<{ index: number } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["gallery"],
    queryFn: () =>
      api.get<GalleryPhoto[]>(`/events/photos/gallery?limit=${PAGE_SIZE}`),
  });

  // Group photos by event so the page renders chronological sections rather
  // than one giant grid.
  const grouped = useMemo(() => {
    const map = new Map<
      number,
      { eventId: number; eventName: string; eventDate: string; photos: GalleryPhoto[] }
    >();
    for (const p of data ?? []) {
      const e = map.get(p.event_id) ?? {
        eventId: p.event_id,
        eventName: p.event_name,
        eventDate: p.event_start_date,
        photos: [],
      };
      e.photos.push(p);
      map.set(p.event_id, e);
    }
    return Array.from(map.values());
  }, [data]);

  const flatPhotos = data ?? [];

  if (isLoading) {
    return (
      <section className="flex flex-col gap-6">
        <Header />
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square w-full" />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <Header
        diasAvailable={flatPhotos.length > 0}
        onDias={() => setDias({ index: 0 })}
      />
      {flatPhotos.length === 0 ? (
        <p className="text-muted-foreground">{da.gallery.empty}</p>
      ) : (
        grouped.map((e) => (
          <EventSection
            key={e.eventId}
            section={e}
            onOpen={(photoId) => {
              const idx = flatPhotos.findIndex((p) => p.id === photoId);
              if (idx >= 0) setDias({ index: idx });
            }}
          />
        ))
      )}
      {dias && (
        <Dias
          photos={flatPhotos}
          index={dias.index}
          onClose={() => setDias(null)}
          onIndex={(i) => setDias({ index: i })}
        />
      )}
    </section>
  );
}

function Header({
  diasAvailable = false,
  onDias,
}: {
  diasAvailable?: boolean;
  onDias?: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-2">
      <div>
        <h1 className="text-2xl font-semibold">{da.gallery.pageTitle}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {da.gallery.pageSubtitle}
        </p>
      </div>
      {diasAvailable && onDias && (
        <Button onClick={onDias}>
          <Play className="size-4" /> {da.gallery.diasMode}
        </Button>
      )}
    </div>
  );
}

function EventSection({
  section,
  onOpen,
}: {
  section: {
    eventId: number;
    eventName: string;
    eventDate: string;
    photos: GalleryPhoto[];
  };
  onOpen: (photoId: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{section.eventName}</h2>
          <p className="text-muted-foreground text-xs">
            {formatDate(section.eventDate)}
          </p>
        </div>
        <Link
          href={`/arrangementer/${section.eventId}`}
          className="text-primary hover:underline text-sm"
        >
          {da.gallery.eventLink}
        </Link>
      </div>
      <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
        {section.photos.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onOpen(p.id)}
            className="group bg-background/40 ring-foreground/10 relative aspect-square overflow-hidden rounded-md ring-1"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={publicUrl(p.url) ?? p.url}
              alt={p.caption ?? ""}
              loading="lazy"
              className="size-full object-cover transition-transform group-hover:scale-105"
            />
            {p.is_group_photo && (
              <Badge
                variant="default"
                className="absolute left-1.5 top-1.5 gap-1 bg-amber-500/90 text-amber-50 backdrop-blur"
              >
                <Star className="size-3 fill-current" />
              </Badge>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

const DIAS_INTERVAL_MS = 4000;

function Dias({
  photos,
  index,
  onClose,
  onIndex,
}: {
  photos: GalleryPhoto[];
  index: number;
  onClose: () => void;
  onIndex: (i: number) => void;
}) {
  const [playing, setPlaying] = useState(true);
  const timerRef = useRef<number | null>(null);
  const photo = photos[index];

  const goPrev = useCallback(
    () => onIndex((index - 1 + photos.length) % photos.length),
    [index, photos.length, onIndex],
  );
  const goNext = useCallback(
    () => onIndex((index + 1) % photos.length),
    [index, photos.length, onIndex],
  );

  // Autoplay tick. Cleared/reset whenever the index changes so the next slide
  // gets a full interval rather than the leftovers of the previous tick.
  useEffect(() => {
    if (!playing) return;
    timerRef.current = window.setTimeout(goNext, DIAS_INTERVAL_MS);
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playing, index, goNext]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
      if (e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, goPrev, goNext]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/95 p-4">
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
        aria-label={da.photos.close}
      >
        <X className="size-5" />
      </button>
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        className="absolute left-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
        aria-label={playing ? da.gallery.diasModeStop : da.gallery.diasMode}
      >
        {playing ? <Pause className="size-5" /> : <Play className="size-5" />}
      </button>
      <button
        type="button"
        onClick={goPrev}
        className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
        aria-label={da.photos.prev}
      >
        <ChevronLeft className="size-6" />
      </button>
      <button
        type="button"
        onClick={goNext}
        className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
        aria-label={da.photos.next}
      >
        <ChevronRight className="size-6" />
      </button>
      <figure className="flex max-h-full max-w-6xl flex-col items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={photo.id}
          src={publicUrl(photo.url) ?? photo.url}
          alt={photo.caption ?? ""}
          className="max-h-[78vh] max-w-full rounded-md object-contain"
        />
        <figcaption className="text-center text-sm text-white/80">
          <p className="font-medium text-white">{photo.event_name}</p>
          {photo.caption && <p className="mt-0.5">{photo.caption}</p>}
          <p className="mt-1 text-xs text-white/50">
            {formatDate(photo.event_start_date)} · {index + 1} / {photos.length}
          </p>
        </figcaption>
      </figure>
    </div>
  );
}
