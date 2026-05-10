"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarPlus } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { KarkovEvent } from "@/lib/types";

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

const schema = z
  .object({
    name: z.string().min(1),
    start_date: z.string().min(1),
    end_date: z.string().min(1),
    bed_count: z.coerce.number().int().min(1).max(200).optional(),
  })
  .refine((v) => v.end_date >= v.start_date, {
    message: "Slutdato skal være på eller efter startdato",
    path: ["end_date"],
  });
type FormValues = z.infer<typeof schema>;

function plusOneYear(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  // Use Date to handle Feb 29 -> Feb 28 gracefully.
  const next = new Date(y + 1, m - 1, d);
  if (next.getMonth() !== m - 1) {
    next.setDate(0);
  }
  const yy = next.getFullYear();
  const mm = String(next.getMonth() + 1).padStart(2, "0");
  const dd = String(next.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function bumpYearInName(name: string): string {
  return name.replace(/(\d{4})/, (_, y) => String(Number(y) + 1));
}

export function PlanNextYearButton({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const isAdmin = user?.role === "admin";

  const defaults = useMemo<FormValues>(
    () => ({
      name: bumpYearInName(event.name),
      start_date: plusOneYear(event.start_date),
      end_date: plusOneYear(event.end_date),
      bed_count: event.bed_count ?? undefined,
    }),
    [event.name, event.start_date, event.end_date, event.bed_count],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
    values: defaults,
  });

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.post<KarkovEvent>("/events", {
        name: v.name,
        start_date: v.start_date,
        end_date: v.end_date,
        address: event.address,
        location_url: event.location_url,
        summerhouse_url: event.summerhouse_url,
        bed_count: v.bed_count ?? null,
        host_user_id: event.host_user_id,
      }),
    onSuccess: (created) => {
      toast.success(da.events.planNextYearCreatedToast);
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["events", "next"] });
      setOpen(false);
      router.push(`/arrangementer/${created.id}`);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  if (!isAdmin) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <CalendarPlus className="size-4" />
          {da.events.planNextYear}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{da.events.planNextYearTitle}</DialogTitle>
          <DialogDescription>{da.events.planNextYearHint}</DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => create.mutate(v))}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="ny-name">{da.events.name}</FieldLabel>
              <Input id="ny-name" {...form.register("name")} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field>
                <FieldLabel htmlFor="ny-start">{da.events.startDate}</FieldLabel>
                <Input id="ny-start" type="date" {...form.register("start_date")} />
              </Field>
              <Field>
                <FieldLabel htmlFor="ny-end">{da.events.endDate}</FieldLabel>
                <Input id="ny-end" type="date" {...form.register("end_date")} />
              </Field>
            </div>
            <Field>
              <FieldLabel htmlFor="ny-beds">
                {da.events.bedCount} {da.common.optional}
              </FieldLabel>
              <Input
                id="ny-beds"
                type="number"
                min={1}
                {...form.register("bed_count")}
              />
            </Field>
            <DialogFooter>
              <Button type="submit" disabled={create.isPending}>
                {da.events.planNextYearCta}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}
