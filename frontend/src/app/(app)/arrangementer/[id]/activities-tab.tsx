"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDate } from "@/lib/format";
import type { EventDay, KarkovEvent } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const schema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  time: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

function NewActivityButton({ event, day }: { event: KarkovEvent; day: EventDay }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", time: "" },
  });

  const onSubmit = async (v: FormValues) => {
    try {
      await api.post(`/events/${event.id}/days/${day.id}/activities`, {
        name: v.name,
        description: v.description || null,
        time: v.time || null,
      });
      toast.success("Aktivitet oprettet");
      setOpen(false);
      form.reset();
      qc.invalidateQueries({ queryKey: ["event", event.id] });
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="size-4" /> {da.activities.add}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {da.activities.add} — {formatDate(day.date)}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="aname">{da.activities.name}</FieldLabel>
              <Input id="aname" {...form.register("name")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="adesc">{da.activities.description}</FieldLabel>
              <Textarea id="adesc" {...form.register("description")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="atime">{da.activities.time}</FieldLabel>
              <Input id="atime" type="time" {...form.register("time")} />
            </Field>
            <DialogFooter>
              <Button type="submit">{da.common.save}</Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ActivitiesTab({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();

  const join = useMutation({
    mutationFn: ({ activityId, userId }: { activityId: number; userId: number }) =>
      api.post(`/activities/${activityId}/attendees`, { user_ids: [userId] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event", event.id] }),
  });
  const leave = useMutation({
    mutationFn: ({ activityId, userId }: { activityId: number; userId: number }) =>
      api.delete(`/activities/${activityId}/attendees/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event", event.id] }),
  });

  return (
    <div className="grid gap-3">
      {event.days.map((day) => (
        <Card key={day.id}>
          <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
            <CardTitle className="text-base capitalize">{formatDate(day.date)}</CardTitle>
            <NewActivityButton event={event} day={day} />
          </CardHeader>
          <CardContent className="grid gap-2">
            {day.activities.length === 0 ? (
              <p className="text-muted-foreground text-sm">{da.activities.none}</p>
            ) : (
              day.activities.map((a) => {
                const joined = user ? a.attendee_user_ids.includes(user.id) : false;
                return (
                  <div
                    key={a.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div>
                      <p className="font-medium">
                        {a.name}
                        {a.time && (
                          <span className="text-muted-foreground ml-2 text-sm">
                            kl. {a.time.slice(0, 5)}
                          </span>
                        )}
                      </p>
                      {a.description && (
                        <p className="text-muted-foreground text-sm">{a.description}</p>
                      )}
                      <p className="text-muted-foreground text-xs">
                        {a.attendee_user_ids.length} tilmeldte
                      </p>
                    </div>
                    {user &&
                      (joined ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            leave.mutate({ activityId: a.id, userId: user.id })
                          }
                        >
                          {da.activities.leave}
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => join.mutate({ activityId: a.id, userId: user.id })}
                        >
                          {da.activities.join}
                        </Button>
                      ))}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
