"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDate } from "@/lib/format";
import type { Chor, KarkovEvent } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/confirm-dialog";

export function ChorsTab({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();

  const assign = useMutation({
    mutationFn: ({ chor, userId }: { chor: Chor; userId: number }) =>
      api.post(`/chors/${chor.id}/assign`, { user_id: userId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event", event.id] }),
    onError: () => toast.error(da.common.error),
  });
  const unassign = useMutation({
    mutationFn: (chor: Chor) => api.post(`/chors/${chor.id}/unassign`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event", event.id] }),
  });

  const isAdmin = user?.role === "admin";
  const removeChor = useMutation({
    mutationFn: (chor: Chor) => api.delete<void>(`/chors/${chor.id}`),
    onSuccess: () => {
      toast.success(da.chors.deletedToast);
      qc.invalidateQueries({ queryKey: ["event", event.id] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const memberById = new Map<number, string>();
  for (const day of event.days) {
    for (const c of day.chors) {
      if (c.assignee_user_id) memberById.set(c.assignee_user_id, `Bruger ${c.assignee_user_id}`);
    }
  }

  const unassigned = event.days
    .flatMap((d) => d.chors.map((c) => ({ ...c, day: d })))
    .filter((c) => c.assignee_user_id === null);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{da.chors.unassignedTitle}</CardTitle>
          <p className="text-muted-foreground text-sm">{da.chors.unassignedDescription}</p>
        </CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {unassigned.length === 0 ? (
            <p className="text-muted-foreground text-sm">Alle opgaver er tildelt — flot!</p>
          ) : (
            unassigned.map((c) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {da.chors.meal[c.meal]} · {da.chors.action[c.action]}
                  </p>
                  <p className="text-muted-foreground text-xs">{formatDate(c.day.date)}</p>
                </div>
                <div className="flex items-center gap-2">
                  {user && (
                    <Button
                      size="sm"
                      onClick={() => assign.mutate({ chor: c, userId: user.id })}
                    >
                      {da.chors.assignSelf}
                    </Button>
                  )}
                  {isAdmin && (
                    <ConfirmDialog
                      trigger={
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          title={da.chors.delete}
                          disabled={removeChor.isPending}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      }
                      title={da.chors.deleteConfirmTitle}
                      description={da.chors.deleteConfirmBody}
                      confirmLabel={da.common.delete}
                      onConfirm={() => removeChor.mutateAsync(c)}
                    />
                  )}
                </div>
              </motion.div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="grid gap-3">
        {event.days.map((day) => (
          <Card key={day.id}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base capitalize">{formatDate(day.date)}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {day.chors.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between rounded-md border p-2"
                >
                  <span className="text-sm">
                    {da.chors.meal[c.meal]} · {da.chors.action[c.action]}
                  </span>
                  <div className="flex items-center gap-2">
                    {c.assignee_user_id ? (
                      <Badge variant="secondary">
                        {da.chors.assignedTo}: {c.assignee_user_id === user?.id ? "dig" : memberById.get(c.assignee_user_id) ?? `Bruger ${c.assignee_user_id}`}
                      </Badge>
                    ) : (
                      <Badge variant="outline">Ledig</Badge>
                    )}
                    {c.assignee_user_id === user?.id && (
                      <Button size="sm" variant="ghost" onClick={() => unassign.mutate(c)}>
                        {da.chors.unassign}
                      </Button>
                    )}
                    {c.assignee_user_id === null && user && (
                      <Button size="sm" onClick={() => assign.mutate({ chor: c, userId: user.id })}>
                        {da.chors.assignSelf}
                      </Button>
                    )}
                    {isAdmin && (
                      <ConfirmDialog
                        trigger={
                          <Button
                            size="icon-sm"
                            variant="ghost"
                            title={da.chors.delete}
                            disabled={removeChor.isPending}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        }
                        title={da.chors.deleteConfirmTitle}
                        description={da.chors.deleteConfirmBody}
                        confirmLabel={da.common.delete}
                        onConfirm={() => removeChor.mutateAsync(c)}
                      />
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
