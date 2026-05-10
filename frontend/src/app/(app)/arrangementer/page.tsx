"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDateRange } from "@/lib/format";
import type { KarkovEvent, User } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
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
  })
  .refine((d) => d.end_date >= d.start_date, {
    path: ["end_date"],
    message: da.events.invalidDates,
  });
type FormValues = z.infer<typeof schema>;

export default function EventsListPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [hostUserId, setHostUserId] = useState<string>(NO_HOST);

  const { data, isLoading } = useQuery({
    queryKey: ["events", "list"],
    queryFn: () => api.get<KarkovEvent[]>("/events"),
  });

  const { data: hostCandidates } = useQuery({
    queryKey: ["users", "hosts"],
    queryFn: () => api.get<User[]>("/users"),
    enabled: user?.role === "admin",
  });
  const hosts = (hostCandidates ?? []).filter((u) => u.role !== "child");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
      address: "",
      location_url: "",
      summerhouse_url: "",
      start_date: "",
      end_date: "",
      bed_count: "",
    },
  });

  const onSubmit = async (v: FormValues) => {
    try {
      const created = await api.post<KarkovEvent>("/events", {
        name: v.name,
        description: v.description || null,
        address: v.address || null,
        location_url: v.location_url || null,
        summerhouse_url: v.summerhouse_url || null,
        start_date: v.start_date,
        end_date: v.end_date,
        bed_count: v.bed_count ? Number(v.bed_count) : null,
        host_user_id: hostUserId !== NO_HOST ? Number(hostUserId) : null,
      });
      toast.success("Arrangement oprettet");
      setOpen(false);
      form.reset();
      setHostUserId(NO_HOST);
      qc.invalidateQueries({ queryKey: ["events"] });
      router.push(`/arrangementer/${created.id}`);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error(da.common.error);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{da.events.list}</h1>
        {user?.role === "admin" && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-4" /> {da.events.create}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>{da.events.create}</DialogTitle>
              </DialogHeader>
              <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="name">{da.events.name}</FieldLabel>
                    <Input id="name" {...form.register("name")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="description">{da.events.description}</FieldLabel>
                    <Textarea id="description" {...form.register("description")} />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="start_date">{da.events.startDate}</FieldLabel>
                      <Input id="start_date" type="date" {...form.register("start_date")} />
                    </Field>
                    <Field data-invalid={!!form.formState.errors.end_date}>
                      <FieldLabel htmlFor="end_date">{da.events.endDate}</FieldLabel>
                      <Input id="end_date" type="date" {...form.register("end_date")} />
                    </Field>
                  </div>
                  <Field>
                    <FieldLabel htmlFor="address">{da.events.address}</FieldLabel>
                    <Input id="address" {...form.register("address")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="location_url">{da.events.locationUrl}</FieldLabel>
                    <Input id="location_url" {...form.register("location_url")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="summerhouse_url">{da.events.summerhouseUrl}</FieldLabel>
                    <Input id="summerhouse_url" {...form.register("summerhouse_url")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="bed_count">{da.events.bedCount}</FieldLabel>
                    <Input id="bed_count" type="number" min={1} {...form.register("bed_count")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="host">{da.events.host}</FieldLabel>
                    <Select value={hostUserId} onValueChange={setHostUserId}>
                      <SelectTrigger id="host" className="w-full">
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
                  <DialogFooter>
                    <Button type="submit">{da.common.save}</Button>
                  </DialogFooter>
                </FieldGroup>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : data && data.length === 0 ? (
        <p className="text-muted-foreground">{da.events.none}</p>
      ) : (
        <ul className="grid gap-3">
          {data?.map((e) => (
            <li key={e.id}>
              <Link href={`/arrangementer/${e.id}`}>
                <Card className="hover:bg-accent/40 transition-colors">
                  <CardHeader className="flex flex-row items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-lg">{e.name}</CardTitle>
                      <p className="text-muted-foreground text-sm">
                        {formatDateRange(e.start_date, e.end_date)}
                      </p>
                      {e.address && (
                        <p className="text-muted-foreground text-sm">{e.address}</p>
                      )}
                    </div>
                    <Badge variant="secondary">{da.events.statusLabels[e.status]}</Badge>
                  </CardHeader>
                  <CardContent className="text-muted-foreground text-sm">
                    {da.events.daysCount(e.days.length)}
                    {e.bed_count && ` · ${da.events.bedCountLabel(e.bed_count)}`}
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
