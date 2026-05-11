"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
  Pencil,
  Star,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { publicUrl } from "@/lib/format";
import type { EventPhoto, KarkovEvent } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

export function PhotosTab({ event }: { event: KarkovEvent }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [editTarget, setEditTarget] = useState<EventPhoto | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { data: photos, isLoading } = useQuery({
    queryKey: ["event-photos", event.id],
    queryFn: () => api.get<EventPhoto[]>(`/events/${event.id}/photos`),
  });

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["event-photos", event.id] });
    qc.invalidateQueries({ queryKey: ["event", event.id] });
    qc.invalidateQueries({ queryKey: ["events"] });
  }, [qc, event.id]);

  const upload = useMutation({
    mutationFn: (files: File[]) =>
      api.uploadMany<EventPhoto[]>(`/events/${event.id}/photos`, files),
    onSuccess: (created) => {
      toast.success(da.photos.uploadedToast(created.length));
      invalidate();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const onFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      const files = Array.from(fileList);
      upload.mutate(files);
    },
    [upload],
  );

  if (isLoading) {
    return (
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full" />
        ))}
      </div>
    );
  }

  const list = photos ?? [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col gap-4"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-muted-foreground text-sm">
          {list.length === 0 ? da.photos.empty : da.photos.count(list.length)}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          multiple
          className="hidden"
          onChange={(e) => {
            onFiles(e.target.files);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
        <Button
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={upload.isPending}
        >
          <Upload className="size-4" />
          {upload.isPending ? da.photos.uploading : da.photos.upload}
        </Button>
      </div>

      {list.length === 0 ? (
        <div className="border-foreground/10 text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
          <ImageIcon className="mx-auto mb-2 size-6 opacity-60" />
          {da.photos.emptyCta}
        </div>
      ) : (
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
          {list.map((p, i) => (
            <PhotoTile
              key={p.id}
              photo={p}
              onClick={() => setLightboxIndex(i)}
              canEdit={canEdit(user?.id, user?.role, event.host_user_id, p)}
              onEdit={() => setEditTarget(p)}
            />
          ))}
        </div>
      )}

      {lightboxIndex !== null && list.length > 0 && (
        <Lightbox
          photos={list}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onIndex={setLightboxIndex}
        />
      )}

      {editTarget && (
        <EditPhotoDialog
          event={event}
          photo={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={invalidate}
        />
      )}
    </motion.div>
  );
}

function canEdit(
  userId: number | undefined,
  role: string | undefined,
  hostId: number | null,
  photo: EventPhoto,
): boolean {
  if (!userId) return false;
  if (role === "admin") return true;
  if (hostId && hostId === userId) return true;
  if (photo.uploader_user_id === userId) return true;
  return false;
}

function PhotoTile({
  photo,
  onClick,
  canEdit,
  onEdit,
}: {
  photo: EventPhoto;
  onClick: () => void;
  canEdit: boolean;
  onEdit: () => void;
}) {
  const src = publicUrl(photo.url) ?? photo.url;
  return (
    <div className="group bg-background/40 ring-foreground/10 relative aspect-square overflow-hidden rounded-md ring-1">
      <button
        type="button"
        onClick={onClick}
        className="absolute inset-0 size-full cursor-zoom-in"
        aria-label={da.photos.open}
      >
        {/* Plain <img> instead of next/image: we serve raw files behind a
            reverse proxy and don't have the optimizer wired up. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={photo.caption ?? ""}
          loading="lazy"
          className="size-full object-cover transition-transform group-hover:scale-105"
        />
      </button>
      {photo.is_group_photo && (
        <Badge
          variant="default"
          className="absolute left-1.5 top-1.5 gap-1 bg-amber-500/90 text-amber-50 backdrop-blur"
        >
          <Star className="size-3 fill-current" />
          {da.photos.groupBadge}
        </Badge>
      )}
      {canEdit && (
        <Button
          size="icon-sm"
          variant="secondary"
          className="absolute right-1.5 top-1.5 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          title={da.photos.edit}
        >
          <Pencil className="size-3.5" />
        </Button>
      )}
    </div>
  );
}

function Lightbox({
  photos,
  index,
  onClose,
  onIndex,
}: {
  photos: EventPhoto[];
  index: number;
  onClose: () => void;
  onIndex: (i: number) => void;
}) {
  const photo = photos[index];
  const goPrev = useCallback(
    () => onIndex((index - 1 + photos.length) % photos.length),
    [index, photos.length, onIndex],
  );
  const goNext = useCallback(
    () => onIndex((index + 1) % photos.length),
    [index, photos.length, onIndex],
  );

  // Keyboard nav: arrows + escape. Re-bound when index changes so prev/next
  // close over the right counters.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, goPrev, goNext]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
      onClick={onClose}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
        aria-label={da.photos.close}
      >
        <X className="size-5" />
      </button>
      {photos.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              goPrev();
            }}
            className="absolute left-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
            aria-label={da.photos.prev}
          >
            <ChevronLeft className="size-6" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              goNext();
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
            aria-label={da.photos.next}
          >
            <ChevronRight className="size-6" />
          </button>
        </>
      )}
      <figure
        className="flex max-h-full max-w-5xl flex-col items-center gap-2"
        onClick={(e) => e.stopPropagation()}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={publicUrl(photo.url) ?? photo.url}
          alt={photo.caption ?? ""}
          className="max-h-[80vh] max-w-full rounded-md object-contain"
        />
        {(photo.caption || photos.length > 1) && (
          <figcaption className="text-center text-sm text-white/90">
            {photo.caption && <p>{photo.caption}</p>}
            {photos.length > 1 && (
              <p className="text-white/60">
                {index + 1} / {photos.length}
              </p>
            )}
          </figcaption>
        )}
      </figure>
    </div>
  );
}

function EditPhotoDialog({
  event,
  photo,
  onClose,
  onSaved,
}: {
  event: KarkovEvent;
  photo: EventPhoto;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [caption, setCaption] = useState(photo.caption ?? "");
  const [isGroup, setIsGroup] = useState(photo.is_group_photo);

  const save = useMutation({
    mutationFn: () =>
      api.patch<EventPhoto>(`/events/${event.id}/photos/${photo.id}`, {
        caption: caption.trim(),
        is_group_photo: isGroup,
      }),
    onSuccess: () => {
      toast.success(da.photos.savedToast);
      onSaved();
      onClose();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const del = useMutation({
    mutationFn: () =>
      api.delete<void>(`/events/${event.id}/photos/${photo.id}`),
    onSuccess: () => {
      toast.success(da.photos.deletedToast);
      onSaved();
      onClose();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const dirty = useMemo(
    () =>
      caption.trim() !== (photo.caption ?? "").trim() ||
      isGroup !== photo.is_group_photo,
    [caption, isGroup, photo.caption, photo.is_group_photo],
  );

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{da.photos.editTitle}</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor={`cap-${photo.id}`}>
              {da.photos.captionLabel}
            </FieldLabel>
            <Textarea
              id={`cap-${photo.id}`}
              value={caption}
              maxLength={500}
              rows={3}
              onChange={(e) => setCaption(e.target.value)}
              placeholder={da.photos.captionPlaceholder}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isGroup}
              onChange={(e) => setIsGroup(e.target.checked)}
            />
            <Star className="size-4 text-amber-500" />
            {da.photos.markGroupLabel}
          </label>
          <DialogFooter className="gap-2 sm:gap-2">
            <ConfirmDialog
              trigger={
                <Button
                  type="button"
                  variant="destructive"
                  disabled={del.isPending}
                  className="mr-auto"
                >
                  <Trash2 className="size-4" />
                  {da.common.delete}
                </Button>
              }
              title={da.photos.deleteConfirmTitle}
              description={da.photos.deleteConfirmBody}
              confirmLabel={da.common.delete}
              onConfirm={() => del.mutateAsync()}
            />
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={save.isPending}
            >
              {da.common.cancel}
            </Button>
            <Button
              type="button"
              onClick={() => save.mutate()}
              disabled={!dirty || save.isPending}
            >
              {da.common.save}
            </Button>
          </DialogFooter>
        </FieldGroup>
      </DialogContent>
    </Dialog>
  );
}
