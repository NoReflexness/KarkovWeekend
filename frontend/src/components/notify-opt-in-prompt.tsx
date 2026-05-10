"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, Clock } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { da } from "@/i18n/da";
import type { NotifyPref } from "@/lib/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function NotifyOptInPrompt() {
  const qc = useQueryClient();
  const [dismissedLocally, setDismissedLocally] = useState(false);

  const { data } = useQuery({
    queryKey: ["notify-pref"],
    queryFn: () => api.get<NotifyPref>("/chat/notify-pref"),
    staleTime: 60_000,
  });

  const setPref = useMutation({
    mutationFn: (notify_email: boolean) =>
      api.put<NotifyPref>("/chat/notify-pref", { notify_email }),
    onSuccess: () => {
      toast.success(da.notify.savedToast);
      qc.invalidateQueries({ queryKey: ["notify-pref"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const dismissServer = useMutation({
    mutationFn: () => api.post<NotifyPref>("/chat/notify-pref/dismiss", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notify-pref"] }),
  });

  const open = !!data?.needs_prompt && !dismissedLocally;

  const choose = (notifyEmail: boolean) => {
    setDismissedLocally(true);
    setPref.mutate(notifyEmail);
  };

  const askLater = () => {
    setDismissedLocally(true);
    dismissServer.mutate();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setDismissedLocally(true);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bell className="size-5" />
            {da.notify.title}
          </DialogTitle>
          <DialogDescription>{da.notify.body}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col-reverse flex-wrap gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button
            variant="ghost"
            className="w-full sm:w-auto"
            onClick={askLater}
          >
            <Clock className="size-4" />
            {da.notify.later}
          </Button>
          <div className="flex flex-col-reverse flex-wrap gap-2 sm:flex-row sm:justify-end">
            <Button
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => choose(false)}
            >
              <BellOff className="size-4" />
              {da.notify.optOut}
            </Button>
            <Button className="w-full sm:w-auto" onClick={() => choose(true)}>
              <Bell className="size-4" />
              {da.notify.optIn}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
