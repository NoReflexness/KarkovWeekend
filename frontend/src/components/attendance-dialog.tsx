"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDate, publicUrl } from "@/lib/format";
import type { EventDay, Family, User } from "@/lib/types";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Manage attendance for a single day across the entire family unit.
 *
 * The dialog pre-selects everyone in the caller's family who is currently
 * marked as present for `day`. On save it diffs the selection against the
 * current state and posts the minimum number of attendance changes:
 *  - Add: users newly checked  -> POST {present: true,  user_ids: [...]}
 *  - Remove: users unchecked   -> POST {present: false, user_ids: [...]}
 */
export function AttendanceDialog({
  eventId,
  day,
  trigger,
  canToggle,
}: {
  eventId: number;
  day: EventDay;
  trigger: React.ReactNode;
  canToggle: boolean;
}) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  const { data: family, isLoading } = useQuery({
    queryKey: ["family", user?.family_id],
    queryFn: () => api.get<Family>(`/families/${user?.family_id}`),
    enabled: open && user?.family_id != null,
  });

  const memberOrder = useMemo(() => {
    if (!family) return [] as User[];
    return [...family.members].sort((a, b) => {
      if (a.role === b.role) return a.name.localeCompare(b.name, "da");
      // Adults before children
      return a.role === "child" ? 1 : -1;
    });
  }, [family]);

  // Map<userId, checked> for the selection currently in the dialog.
  const [selection, setSelection] = useState<Record<number, boolean>>({});

  // Initialize selection from current attendees of this day, defaulting any
  // family members who aren't currently present to "checked" so a fresh sign-up
  // implicitly opts the whole family in.
  useEffect(() => {
    if (!open || !family) return;
    const current = new Set(day.attendee_user_ids);
    const next: Record<number, boolean> = {};
    const noneAttending = !family.members.some((m) => current.has(m.id));
    for (const m of family.members) {
      next[m.id] = noneAttending ? true : current.has(m.id);
    }
    setSelection(next);
  }, [open, family, day.attendee_user_ids]);

  const save = useMutation({
    mutationFn: async () => {
      const currentlyPresent = new Set(day.attendee_user_ids);
      const wantPresent = new Set(
        Object.entries(selection)
          .filter(([, v]) => v)
          .map(([k]) => Number(k)),
      );

      const toAdd = Array.from(wantPresent).filter(
        (id) => !currentlyPresent.has(id),
      );
      const toRemove = Array.from(currentlyPresent).filter(
        (id) => !wantPresent.has(id) && memberIds.has(id),
      );

      if (toAdd.length > 0) {
        await api.post(`/events/${eventId}/days/${day.id}/attendance`, {
          present: true,
          user_ids: toAdd,
        });
      }
      if (toRemove.length > 0) {
        await api.post(`/events/${eventId}/days/${day.id}/attendance`, {
          present: false,
          user_ids: toRemove,
        });
      }
    },
    onSuccess: () => {
      toast.success(da.events.attendance.savedToast);
      qc.invalidateQueries({ queryKey: ["event", eventId] });
      setOpen(false);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error(da.common.error);
    },
  });

  const memberIds = useMemo(
    () => new Set((family?.members ?? []).map((m) => m.id)),
    [family],
  );

  const toggle = (id: number) =>
    setSelection((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {da.events.attendance.dialogTitle(formatDate(day.date))}
          </DialogTitle>
          <DialogDescription>{da.events.attendance.hint}</DialogDescription>
        </DialogHeader>
        {!user?.family_id && (
          <p className="text-muted-foreground text-sm">
            {da.events.attendance.noFamily}
          </p>
        )}
        {isLoading && <Skeleton className="h-32 w-full" />}
        {family && (
          <div className="grid gap-2">
            {memberOrder.map((m) => (
              <label
                key={m.id}
                className="flex items-center gap-3 rounded-md border px-3 py-2 cursor-pointer"
              >
                <Checkbox
                  checked={!!selection[m.id]}
                  onCheckedChange={() => toggle(m.id)}
                  disabled={!canToggle}
                />
                <Avatar className="size-7">
                  {m.profile_picture_url && (
                    <AvatarImage
                      src={publicUrl(m.profile_picture_url)}
                      alt={m.name}
                    />
                  )}
                  <AvatarFallback>
                    {m.name.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex flex-col flex-1 min-w-0">
                  <span className="truncate text-sm font-medium">{m.name}</span>
                  <span className="text-muted-foreground text-xs capitalize">
                    {m.role === "child" ? da.profile.childrenHeading.toLowerCase() : ""}
                  </span>
                </div>
              </label>
            ))}
          </div>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={save.isPending}
          >
            {da.common.cancel}
          </Button>
          <Button
            type="button"
            onClick={() => save.mutate()}
            disabled={!canToggle || !family || save.isPending}
          >
            {da.events.attendance.saveButton}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
