"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Calendar,
  CalendarPlus,
  Hand,
  Send,
  Sparkles,
  Trash2,
  Trophy,
  UserCheck,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";

import { api, API_BASE, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { ChatMessage, ChatReadState } from "@/lib/types";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const ICON_MAP: Record<string, typeof Sparkles> = {
  "calendar-plus": CalendarPlus,
  calendar: Calendar,
  "user-check": UserCheck,
  sparkles: Sparkles,
  "user-plus": UserPlus,
  hand: Hand,
  trophy: Trophy,
};

function formatDateLabel(d: Date): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(d);
  target.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - target.getTime()) / 86400000);
  if (diffDays === 0) return da.chat.today;
  if (diffDays === 1) return da.chat.yesterday;
  return target.toLocaleDateString("da-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatTime(s: string): string {
  return new Date(s).toLocaleTimeString("da-DK", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// How long the chat must stay visible after a render before we mark the
// currently-displayed messages as read. Long enough to feel deliberate, short
// enough that opening the page and tabbing away still counts as "read".
const READ_DWELL_MS = 2500;

// Treat the user as "pinned to the bottom" when they're within this many
// pixels of it; if so, new messages auto-scroll. Otherwise we leave the
// scroll position alone (e.g. when they're reading the unread divider).
const STICK_TO_BOTTOM_THRESHOLD_PX = 80;

export default function ChatPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const dividerRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");

  const { data: messages, isLoading } = useQuery({
    queryKey: ["chat", "messages"],
    queryFn: () => api.get<ChatMessage[]>("/chat/messages?limit=200"),
    // SSE pushes new messages as they arrive (see effect below). When the
    // browser is missing EventSource (very rare) or the connection is broken
    // for a while, this 30 s safety-net poll catches up.
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  });

  // Live updates via Server-Sent Events. We append new messages directly into
  // the cached query data so the UI doesn't need to re-fetch the full list.
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    const lastId =
      (messages && messages.length > 0
        ? Math.max(...messages.map((m) => m.id))
        : 0) ?? 0;
    const url = `${API_BASE}/chat/stream?since_id=${lastId}`;
    const es = new EventSource(url, { withCredentials: true });
    es.addEventListener("messages", (ev) => {
      try {
        const incoming = JSON.parse((ev as MessageEvent).data) as ChatMessage[];
        if (!Array.isArray(incoming) || incoming.length === 0) return;
        qc.setQueryData<ChatMessage[]>(["chat", "messages"], (prev) => {
          const prior = prev ?? [];
          const known = new Set(prior.map((m) => m.id));
          const merged = [...prior];
          for (const m of incoming) {
            if (!known.has(m.id)) merged.push(m);
          }
          merged.sort((a, b) => a.id - b.id);
          return merged;
        });
      } catch {
        // Ignore malformed payloads; the safety-net poll will catch up.
      }
    });
    es.addEventListener("bye", () => es.close());
    es.onerror = () => {
      // EventSource auto-reconnects; nothing to do here.
    };
    return () => {
      es.close();
    };
    // We intentionally only reopen the stream when the *first* batch arrives.
    // Reopening on every message would be wasteful, and the stream itself
    // walks `since_id` forward internally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc, isLoading]);

  // ---- Read-state / unread divider --------------------------------------
  //
  // We snapshot the server's "last read" id once on mount and *keep it
  // stable for the visit*. That way the "—— Nye beskeder ——" divider
  // doesn't disappear out from under the user as soon as we advance the
  // marker on the server.
  const { data: serverReadState } = useQuery({
    queryKey: ["chat", "read-state"],
    queryFn: () => api.get<ChatReadState>("/chat/read-state"),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
  const unreadAnchorRef = useRef<number | null>(null);
  if (unreadAnchorRef.current === null && serverReadState) {
    unreadAnchorRef.current = serverReadState.last_read_message_id;
  }
  const unreadAnchor = unreadAnchorRef.current;

  // First message id strictly greater than the snapshot, if any.
  const firstUnreadId = useMemo(() => {
    if (unreadAnchor === null) return null;
    if (!messages || messages.length === 0) return null;
    const m = messages.find((m) => m.id > unreadAnchor);
    return m ? m.id : null;
  }, [messages, unreadAnchor]);

  // One-shot initial scroll. After the first non-empty render we either
  // bring the divider into view (so the user lands on what they missed) or
  // — if there's nothing unread — scroll to the bottom like before.
  const didInitialScrollRef = useRef(false);
  useEffect(() => {
    if (didInitialScrollRef.current) return;
    if (isLoading || !messages) return;
    didInitialScrollRef.current = true;
    requestAnimationFrame(() => {
      if (firstUnreadId !== null && dividerRef.current) {
        dividerRef.current.scrollIntoView({ block: "start" });
      } else if (scrollerRef.current) {
        scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
      }
    });
  }, [isLoading, messages, firstUnreadId]);

  // For subsequent renders, only autoscroll when the user is already near
  // the bottom — never yank them away from the divider they're reading.
  const wasNearBottomRef = useRef(true);
  useEffect(() => {
    if (!didInitialScrollRef.current) return;
    const el = scrollerRef.current;
    if (!el) return;
    if (wasNearBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);
  const handleScroll = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
    wasNearBottomRef.current = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD_PX;
  }, []);

  // Advance the marker on the server. Monotonic on the backend, so it's
  // safe to send the same id more than once.
  const advanceReadMarker = useCallback(
    (id: number) => {
      if (id <= 0) return;
      const current = unreadAnchorRef.current ?? 0;
      // Don't bother the server with no-ops, but always send if we are
      // crossing the snapshot for the first time.
      if (id <= current && current !== unreadAnchor) return;
      void api
        .put<ChatReadState>("/chat/read-state", { last_read_message_id: id })
        .catch(() => {
          /* swallow — next visit will retry */
        });
    },
    [unreadAnchor],
  );

  // Track the highest id we've actually rendered. Updated on every message
  // change so the dwell + visibility flush always send the latest known id.
  const latestRenderedIdRef = useRef(0);
  useEffect(() => {
    if (!messages || messages.length === 0) return;
    latestRenderedIdRef.current = Math.max(
      latestRenderedIdRef.current,
      ...messages.map((m) => m.id),
    );
  }, [messages]);

  // Dwell timer: after the user has been staring at chat for a couple of
  // seconds we mark everything visible as read.
  useEffect(() => {
    if (!messages || messages.length === 0) return;
    const t = window.setTimeout(() => {
      advanceReadMarker(latestRenderedIdRef.current);
    }, READ_DWELL_MS);
    return () => window.clearTimeout(t);
  }, [messages, advanceReadMarker]);

  // Flush on tab-hide / unmount so the marker stays accurate even if the
  // user closes the tab before the dwell timer fires.
  useEffect(() => {
    const flush = () => {
      const id = latestRenderedIdRef.current;
      if (id <= 0) return;
      try {
        const url = `${API_BASE}/chat/read-state`;
        const blob = new Blob(
          [JSON.stringify({ last_read_message_id: id })],
          { type: "application/json" },
        );
        if (
          typeof navigator !== "undefined" &&
          typeof navigator.sendBeacon === "function" &&
          navigator.sendBeacon(url, blob)
        ) {
          return;
        }
      } catch {
        /* fall through to the regular API */
      }
      advanceReadMarker(id);
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flush();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      flush();
    };
  }, [advanceReadMarker]);

  const send = useMutation({
    mutationFn: (body: string) => api.post<ChatMessage>("/chat/messages", { body }),
    onSuccess: () => {
      setText("");
      // Posting a message implies we've seen everything that came before.
      wasNearBottomRef.current = true;
      qc.invalidateQueries({ queryKey: ["chat", "messages"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete<void>(`/chat/messages/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat", "messages"] }),
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  // Group messages by local date for clean separators.
  const grouped = useMemo(() => {
    const out: { label: string; items: ChatMessage[] }[] = [];
    for (const m of messages ?? []) {
      const label = formatDateLabel(new Date(m.created_at));
      const tail = out[out.length - 1];
      if (tail && tail.label === label) tail.items.push(m);
      else out.push({ label, items: [m] });
    }
    return out;
  }, [messages]);

  return (
    <Card className="flex h-[calc(100svh-12rem)] flex-col overflow-hidden md:h-[calc(100svh-9rem)]">
      <CardHeader className="border-b pb-3">
        <CardTitle className="text-lg">{da.chat.title}</CardTitle>
        <p className="text-muted-foreground text-xs">{da.chat.subtitle}</p>
      </CardHeader>
      <CardContent
        ref={scrollerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 py-4 sm:px-6"
      >
        {isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-10 w-1/2" />
          </div>
        ) : grouped.length === 0 ? (
          <p className="text-muted-foreground py-12 text-center text-sm">
            {da.chat.empty}
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {grouped.map((group) => (
              <section key={group.label} className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <div className="bg-foreground/10 h-px flex-1" />
                  <span className="text-muted-foreground text-xs uppercase tracking-wide">
                    {group.label}
                  </span>
                  <div className="bg-foreground/10 h-px flex-1" />
                </div>
                {group.items.map((m) => (
                  <div
                    key={m.id}
                    ref={m.id === firstUnreadId ? dividerRef : undefined}
                    className="flex flex-col gap-2 scroll-mt-4"
                  >
                    {m.id === firstUnreadId && (
                      <div className="flex items-center gap-2 pt-1">
                        <div className="bg-primary/40 h-px flex-1" />
                        <span className="bg-primary/15 text-primary rounded-full px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide">
                          {da.chat.unreadDivider}
                        </span>
                        <div className="bg-primary/40 h-px flex-1" />
                      </div>
                    )}
                    <MessageRow
                      msg={m}
                      isOwn={!!user && m.user_id === user.id}
                      isAdmin={user?.role === "admin"}
                      onDelete={() => remove.mutate(m.id)}
                    />
                  </div>
                ))}
              </section>
            ))}
          </div>
        )}
      </CardContent>
      <form
        className="bg-background/40 border-t p-3 sm:p-4"
        onSubmit={(e) => {
          e.preventDefault();
          const v = text.trim();
          if (!v) return;
          send.mutate(v);
        }}
      >
        <div className="flex gap-2">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={da.chat.placeholder}
            maxLength={2000}
          />
          <Button type="submit" disabled={send.isPending || text.trim().length === 0}>
            <Send className="size-4" />
            <span className="hidden sm:inline">{da.chat.send}</span>
          </Button>
        </div>
      </form>
    </Card>
  );
}

function MessageRow({
  msg,
  isOwn,
  isAdmin,
  onDelete,
}: {
  msg: ChatMessage;
  isOwn: boolean;
  isAdmin: boolean;
  onDelete: () => void;
}) {
  if (msg.kind === "system") {
    const Icon = (msg.icon && ICON_MAP[msg.icon]) || Sparkles;
    return (
      <div className="flex items-start gap-3">
        <div className="from-primary/20 to-primary/10 text-primary mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ring-1 ring-foreground/10">
          <Icon className="size-4" />
        </div>
        <div className="bg-background/40 ring-foreground/10 flex-1 rounded-2xl px-3 py-2 ring-1">
          <div className="text-muted-foreground mb-0.5 flex items-center gap-2 text-xs">
            <span className="bg-primary/10 text-primary rounded-full px-2 py-0.5 text-[0.65rem] uppercase tracking-wide">
              {da.chat.systemBadge}
            </span>
            <span>{formatTime(msg.created_at)}</span>
          </div>
          <p className="text-sm">
            {msg.related_event_id ? (
              <Link
                href={`/arrangementer/${msg.related_event_id}`}
                className="hover:underline"
              >
                {msg.body}
              </Link>
            ) : (
              msg.body
            )}
          </p>
        </div>
        {isAdmin && (
          <Button
            size="icon-sm"
            variant="ghost"
            title={da.chat.deleteSystemAdmin}
            onClick={onDelete}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
    );
  }

  const initials =
    msg.user_name
      ?.split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("") ?? "?";

  return (
    <div
      className={`flex items-start gap-3 ${isOwn ? "flex-row-reverse" : ""}`}
    >
      <Avatar className="size-8">
        <AvatarFallback>{initials}</AvatarFallback>
      </Avatar>
      <div
        className={`max-w-[78%] rounded-2xl px-3 py-2 ring-1 ${
          isOwn
            ? "bg-primary text-primary-foreground ring-primary/30"
            : "bg-background/60 ring-foreground/10"
        }`}
      >
        <div
          className={`mb-0.5 flex items-center gap-2 text-xs ${
            isOwn ? "text-primary-foreground/80" : "text-muted-foreground"
          }`}
        >
          <span className="font-medium">{msg.user_name ?? "?"}</span>
          <span>{formatTime(msg.created_at)}</span>
        </div>
        <p className="whitespace-pre-wrap text-sm">{msg.body}</p>
      </div>
      {isOwn && (
        <Button
          size="icon-sm"
          variant="ghost"
          title={da.chat.deleteOwn}
          onClick={onDelete}
        >
          <Trash2 className="size-4" />
        </Button>
      )}
    </div>
  );
}
