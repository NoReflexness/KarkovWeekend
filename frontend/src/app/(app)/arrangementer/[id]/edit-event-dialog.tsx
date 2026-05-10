"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { KarkovEvent, User } from "@/lib/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const NO_HOST = "__none__";

const schema = z
  .object({
    name: z.string().min(1),
    description: z.string().optional(),
    address: z.string().optional(),
    location_url: z.string().optional(),
    summerhouse_url: z.string().optional(),
    start_date: z.string(),
    end_date: z.string(),
    bed_count: z.string().optional(),
    host_user_id: z.string().optional(),
  })
  .refine((d) => d.end_date >= d.start_date, {
    path: ["end_date"],
    message: da.events.invalidDates,
  });
type FormValues = z.infer<typeof schema>;

export function EditEventDialog({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const isAdmin = user?.role === "admin";
  const isHost = user?.id === event.host_user_id;

  // Always call hooks in the same order; gate render at the end.
  const { data: hostCandidates } = useQuery({
    queryKey: ["users", "hosts"],
    queryFn: () => api.get<User[]>("/users"),
    enabled: open,
  });
  const hosts = useMemo(
    () => (hostCandidates ?? []).filter((u) => u.role !== "child"),
    [hostCandidates],
  );

  const defaults = useMemo<FormValues>(
    () => ({
      name: event.name,
      description: event.description ?? "",
      address: event.address ?? "",
      location_url: event.location_url ?? "",
      summerhouse_url: event.summerhouse_url ?? "",
      start_date: event.start_date,
      end_date: event.end_date,
      bed_count: event.bed_count != null ? String(event.bed_count) : "",
      host_user_id: event.host_user_id ? String(event.host_user_id) : NO_HOST,
    }),
    [event],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
    values: defaults,
  });

  const update = useMutation({
    mutationFn: (v: FormValues) =>
      api.patch<KarkovEvent>(`/events/${event.id}`, {
        name: v.name,
        description: v.description || null,
        address: v.address || null,
        location_url: v.location_url || null,
        summerhouse_url: v.summerhouse_url || null,
        start_date: v.start_date,
        end_date: v.end_date,
        bed_count: v.bed_count ? Number(v.bed_count) : null,
        // Only admins may change the host; for hosts the field is read-only.
        host_user_id: isAdmin
          ? v.host_user_id && v.host_user_id !== NO_HOST
            ? Number(v.host_user_id)
            : null
          : event.host_user_id,
      }),
    onSuccess: () => {
      toast.success(da.events.editedToast);
      qc.invalidateQueries({ queryKey: ["event", event.id] });
      qc.invalidateQueries({ queryKey: ["events"] });
      setOpen(false);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  if (!isAdmin && !isHost) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Pencil className="size-4" />
          {da.events.edit}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{da.events.editTitle}</DialogTitle>
          <DialogDescription>{da.events.editHint}</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((v) => update.mutate(v))}
          noValidate
          className="max-h-[70svh] overflow-y-auto"
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="ed-name">{da.events.name}</FieldLabel>
              <Input id="ed-name" {...form.register("name")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="ed-desc">{da.events.description}</FieldLabel>
              <Textarea id="ed-desc" {...form.register("description")} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field>
                <FieldLabel htmlFor="ed-start">{da.events.startDate}</FieldLabel>
                <Input id="ed-start" type="date" {...form.register("start_date")} />
              </Field>
              <Field data-invalid={!!form.formState.errors.end_date}>
                <FieldLabel htmlFor="ed-end">{da.events.endDate}</FieldLabel>
                <Input id="ed-end" type="date" {...form.register("end_date")} />
              </Field>
            </div>
            <Field>
              <FieldLabel htmlFor="ed-address">{da.events.address}</FieldLabel>
              <Input id="ed-address" {...form.register("address")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="ed-loc">{da.events.locationUrl}</FieldLabel>
              <Input id="ed-loc" {...form.register("location_url")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="ed-sh">{da.events.summerhouseUrl}</FieldLabel>
              <Input id="ed-sh" {...form.register("summerhouse_url")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="ed-beds">{da.events.bedCount}</FieldLabel>
              <Input
                id="ed-beds"
                type="number"
                min={1}
                {...form.register("bed_count")}
              />
            </Field>
            {isAdmin && (
              <Field>
                <FieldLabel htmlFor="ed-host">{da.events.host}</FieldLabel>
                <Select
                  value={form.watch("host_user_id") ?? NO_HOST}
                  onValueChange={(v) => form.setValue("host_user_id", v)}
                >
                  <SelectTrigger id="ed-host" className="w-full">
                    <SelectValue placeholder={da.events.noHost} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_HOST}>{da.events.noHost}</SelectItem>
                    {hosts.map((h) => (
                      <SelectItem key={h.id} value={String(h.id)}>
                        {h.name}
                        {h.email ? ` · ${h.email}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-muted-foreground text-xs">{da.events.hostHint}</p>
              </Field>
            )}
            <DialogFooter>
              <Button type="submit" disabled={update.isPending}>
                {da.common.save}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}
