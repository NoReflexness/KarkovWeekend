"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { ChatMessage } from "@/lib/types";

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

export default function ChatPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");

  const { data: messages, isLoading } = useQuery({
    queryKey: ["chat", "messages"],
    queryFn: () => api.get<ChatMessage[]>("/chat/messages?limit=200"),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const send = useMutation({
    mutationFn: (body: string) => api.post<ChatMessage>("/chat/messages", { body }),
    onSuccess: () => {
      setText("");
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

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <Card className="flex h-[calc(100svh-12rem)] flex-col overflow-hidden md:h-[calc(100svh-9rem)]">
      <CardHeader className="border-b pb-3">
        <CardTitle className="text-lg">{da.chat.title}</CardTitle>
        <p className="text-muted-foreground text-xs">{da.chat.subtitle}</p>
      </CardHeader>
      <CardContent
        ref={scrollerRef}
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
                  <MessageRow
                    key={m.id}
                    msg={m}
                    isOwn={!!user && m.user_id === user.id}
                    isAdmin={user?.role === "admin"}
                    onDelete={() => remove.mutate(m.id)}
                  />
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
