"use client";

import { useEffect, useState } from "react";
import { Bell, BellOff, Smartphone } from "lucide-react";
import { toast } from "sonner";

import { da } from "@/i18n/da";
import {
  ensureSubscribed,
  getCurrentSubscription,
  pushAvailability,
  unsubscribe,
} from "@/lib/push";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

type State = "loading" | "insecure" | "unsupported" | "denied" | "off" | "on";

export function PushToggle() {
  const [state, setState] = useState<State>("loading");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const availability = pushAvailability();
      if (availability === "insecure-context") {
        if (!cancelled) setState("insecure");
        return;
      }
      if (availability !== "available") {
        if (!cancelled) setState("unsupported");
        return;
      }
      if (Notification.permission === "denied") {
        if (!cancelled) setState("denied");
        return;
      }
      const sub = await getCurrentSubscription();
      if (!cancelled) setState(sub ? "on" : "off");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const enable = async () => {
    setBusy(true);
    try {
      await ensureSubscribed();
      setState("on");
      toast.success(da.profile.pushEnabled);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : da.common.error;
      toast.error(msg);
      if (typeof Notification !== "undefined" && Notification.permission === "denied") {
        setState("denied");
      }
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    try {
      await unsubscribe();
      setState("off");
      toast.success(da.profile.pushDisabled);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : da.common.error;
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-3 rounded-lg border p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Smartphone className="size-4" />
        {da.profile.pushTitle}
      </div>
      <p className="text-muted-foreground text-xs">{da.profile.pushHint}</p>
      {state === "insecure" && (
        <p className="text-muted-foreground text-xs">{da.profile.pushInsecure}</p>
      )}
      {state === "unsupported" && (
        <p className="text-muted-foreground text-xs">{da.profile.pushUnsupported}</p>
      )}
      {state === "denied" && (
        <p className="text-destructive text-xs">{da.profile.pushDenied}</p>
      )}
      {(state === "on" || state === "off" || state === "loading") && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-xs uppercase tracking-wide">
            {state === "on" ? da.profile.pushEnabled : da.profile.pushDisabled}
          </span>
          {state === "on" ? (
            <Button size="sm" variant="outline" onClick={disable} disabled={busy}>
              <BellOff className="size-4" />
              {busy ? da.profile.pushSaving : da.profile.pushDisable}
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={enable}
              disabled={busy || state === "loading"}
            >
              <Bell className="size-4" />
              {busy ? da.profile.pushSaving : da.profile.pushEnable}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
