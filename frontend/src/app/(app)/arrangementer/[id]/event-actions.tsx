"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { Expense, ExpenseCategory, KarkovEvent } from "@/lib/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function EventActions({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isHostOrAdmin = user?.role === "admin" || user?.id === event.host_user_id;
  const [confirmOpen, setConfirmOpen] = useState(false);

  const open = useMutation({
    mutationFn: () => api.post(`/events/${event.id}/open`),
    onSuccess: () => {
      toast.success("Tilmelding åbnet");
      qc.invalidateQueries({ queryKey: ["event", event.id] });
      qc.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });
  const lock = useMutation({
    mutationFn: () => api.post(`/events/${event.id}/lock-attendance`),
    onSuccess: () => {
      toast.success("Tilmelding låst");
      qc.invalidateQueries({ queryKey: ["event", event.id] });
      qc.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });
  const finalize = useMutation({
    mutationFn: () => api.post(`/events/${event.id}/finalize`),
    onSuccess: () => {
      toast.success("Arrangement afsluttet");
      setConfirmOpen(false);
      qc.invalidateQueries({ queryKey: ["event", event.id] });
      qc.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  // Used to enrich the confirm dialog with a utilities-pending warning.
  const { data: categories } = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => api.get<ExpenseCategory[]>("/expense-categories"),
    enabled: isHostOrAdmin,
  });
  const { data: expenses } = useQuery({
    queryKey: ["expenses", event.id],
    queryFn: () => api.get<Expense[]>(`/events/${event.id}/expenses`),
    enabled: isHostOrAdmin,
  });
  const utilityPendingNames = (categories ?? [])
    .filter((c) => c.is_utility)
    .filter(
      (c) => !(expenses ?? []).some((e) => e.category_id === c.id),
    )
    .map((c) => c.name);

  if (!isHostOrAdmin) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {event.status === "planlagt" && (
        <Button size="sm" onClick={() => open.mutate()}>
          {da.events.open}
        </Button>
      )}
      {event.status === "aabent" && (
        <Button size="sm" variant="secondary" onClick={() => lock.mutate()}>
          {da.events.lockAttendance}
        </Button>
      )}
      {event.status !== "afsluttet" && event.status !== "planlagt" && (
        <>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => setConfirmOpen(true)}
          >
            {da.events.finalize}
          </Button>
          <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{da.budget.finalizeConfirmTitle}</DialogTitle>
                <DialogDescription>
                  {utilityPendingNames.length > 0
                    ? da.budget.finalizeConfirmWithUtilitiesBody
                    : da.budget.finalizeConfirmBody}
                </DialogDescription>
              </DialogHeader>
              {utilityPendingNames.length > 0 && (
                <p className="text-sm">
                  {da.budget.utilitiesPendingBody(utilityPendingNames.join(", "))}
                </p>
              )}
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setConfirmOpen(false)}
                >
                  {da.common.cancel}
                </Button>
                <Button
                  variant="destructive"
                  disabled={finalize.isPending}
                  onClick={() => finalize.mutate()}
                >
                  {da.budget.finalizeConfirmCta}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  );
}
