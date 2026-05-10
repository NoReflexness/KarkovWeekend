"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Mail } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type { Family, Invite, PricingRules, User } from "@/lib/types";
import { ageOn, categoryLabel, categoryVariant, classifyAge } from "@/lib/age";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
import { Skeleton } from "@/components/ui/skeleton";

const childSchema = z.object({
  name: z.string().min(1),
  birthdate: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  password: z.string().min(8).optional().or(z.literal("")),
});
type ChildForm = z.infer<typeof childSchema>;

const inviteSchema = z.object({ email: z.string().email() });
type InviteForm = z.infer<typeof inviteSchema>;

export default function FamilyPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [childOpen, setChildOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [pendingInvite, setPendingInvite] = useState<Invite | null>(null);

  const familyId = user?.family_id;
  const { data: family, isLoading } = useQuery({
    queryKey: ["family", familyId],
    queryFn: () => api.get<Family>(`/families/${familyId}`),
    enabled: !!familyId,
  });
  const { data: children } = useQuery({
    queryKey: ["my-children"],
    queryFn: () => api.get<User[]>("/me/children"),
  });
  const { data: pricing } = useQuery({
    queryKey: ["pricing-rules"],
    queryFn: () => api.get<PricingRules>("/pricing-rules"),
  });

  const childForm = useForm<ChildForm>({
    resolver: zodResolver(childSchema),
    defaultValues: { name: "", birthdate: "", email: "", password: "" },
  });
  const inviteForm = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "" },
  });

  const createChild = useMutation({
    mutationFn: (v: ChildForm) =>
      api.post<User>("/me/children", {
        name: v.name,
        birthdate: v.birthdate,
        email: v.email || null,
        password: v.password || null,
      }),
    onSuccess: () => {
      toast.success("Barn tilføjet");
      setChildOpen(false);
      childForm.reset();
      qc.invalidateQueries({ queryKey: ["my-children"] });
      qc.invalidateQueries({ queryKey: ["family", familyId] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const invite = useMutation({
    mutationFn: (v: InviteForm) =>
      api.post<Invite>(`/families/${familyId}/invites`, { email: v.email }),
    onSuccess: (data) => {
      setPendingInvite(data);
      toast.success(da.family.inviteSent);
      qc.invalidateQueries({ queryKey: ["family", familyId] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  if (!familyId) {
    return <p className="text-muted-foreground">Du tilhører ikke en familie endnu.</p>;
  }
  if (isLoading || !family) {
    return <Skeleton className="h-64 w-full" />;
  }

  const inviteUrl = pendingInvite
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/registrer?token=${pendingInvite.token}`
    : null;

  return (
    <section className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{family.name}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          <p className="text-muted-foreground text-sm">{da.family.members}</p>
          {family.members
            .filter((m) => m.role !== "child")
            .map((m) => (
              <div key={m.id} className="flex items-center gap-3 rounded-md border p-3">
                <Avatar className="size-9">
                  <AvatarFallback>{m.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="text-sm">
                  <p className="font-medium">{m.name}</p>
                  <p className="text-muted-foreground">{m.email}</p>
                </div>
              </div>
            ))}
          {user?.role === "admin" && (
            <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="w-fit">
                  <Mail className="size-4" /> {da.family.invite}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{da.family.invite}</DialogTitle>
                </DialogHeader>
                <form onSubmit={inviteForm.handleSubmit((v) => invite.mutate(v))}>
                  <FieldGroup>
                    <Field>
                      <FieldLabel htmlFor="invite-email">{da.auth.email}</FieldLabel>
                      <Input id="invite-email" type="email" {...inviteForm.register("email")} />
                    </Field>
                    {inviteUrl && (
                      <div className="rounded-md border p-3 text-sm">
                        <p className="text-muted-foreground mb-2">{da.family.inviteCopyHint}</p>
                        <code className="break-all text-xs">{inviteUrl}</code>
                      </div>
                    )}
                    <DialogFooter>
                      <Button type="submit">{da.common.save}</Button>
                    </DialogFooter>
                  </FieldGroup>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{da.family.children}</CardTitle>
          <Dialog open={childOpen} onOpenChange={setChildOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="size-4" /> {da.family.addChild}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{da.family.addChild}</DialogTitle>
              </DialogHeader>
              <form onSubmit={childForm.handleSubmit((v) => createChild.mutate(v))}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="cname">{da.profile.name}</FieldLabel>
                    <Input id="cname" {...childForm.register("name")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="cbd">{da.profile.birthdate}</FieldLabel>
                    <Input id="cbd" type="date" {...childForm.register("birthdate")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="cemail">
                      {da.auth.email} {da.common.optional}
                    </FieldLabel>
                    <Input id="cemail" type="email" {...childForm.register("email")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="cpw">
                      {da.auth.password} {da.common.optional}
                    </FieldLabel>
                    <Input id="cpw" type="password" {...childForm.register("password")} />
                  </Field>
                  <DialogFooter>
                    <Button type="submit">{da.common.save}</Button>
                  </DialogFooter>
                </FieldGroup>
              </form>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent className="grid gap-2">
          {children && children.length === 0 && (
            <p className="text-muted-foreground text-sm">Ingen børn endnu.</p>
          )}
          {children?.map((c) => {
            const age = ageOn(c.birthdate);
            const cat = classifyAge(age, pricing);
            return (
              <div
                key={c.id}
                className="flex items-center gap-3 rounded-md border p-3"
              >
                <Avatar className="size-9">
                  <AvatarFallback>{c.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="text-sm flex-1 min-w-0">
                  <p className="font-medium">{c.name}</p>
                  <p className="text-muted-foreground">
                    {c.birthdate
                      ? `f. ${c.birthdate}${age !== null ? ` · ${age} år` : ""}`
                      : ""}
                  </p>
                </div>
                {cat !== "unknown" && (
                  <Badge variant={categoryVariant(cat)}>{categoryLabel(cat)}</Badge>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </section>
  );
}
