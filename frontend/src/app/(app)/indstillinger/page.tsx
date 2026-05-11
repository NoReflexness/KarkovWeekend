"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Plus,
  Mail,
  Baby,
  UserPlus,
  Send,
  ShieldCheck,
  Shield,
  Trash2,
  Pencil,
  Download,
  Upload,
  Link2,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import type {
  ExpenseCategory,
  Family,
  Invite,
  InviteSendResult,
  PricingRules,
  User,
} from "@/lib/types";
import { ageOn, categoryLabel, categoryVariant, classifyAge } from "@/lib/age";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  EditChildDialog,
  EditFamilyDialog,
} from "@/components/admin-edit-dialogs";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const pricingSchema = z
  .object({
    baby_max_age: z.number().int().min(0).max(18),
    kid_max_age: z.number().int().min(1).max(21),
  })
  .refine((d) => d.baby_max_age < d.kid_max_age, {
    message: "Baby alder skal være mindre end kid alder",
    path: ["kid_max_age"],
  });
type PricingForm = z.infer<typeof pricingSchema>;

const familySchema = z.object({ name: z.string().min(1) });
type FamilyForm = z.infer<typeof familySchema>;

const inviteSchema = z.object({ email: z.string().email() });
type InviteForm = z.infer<typeof inviteSchema>;

const childSchema = z.object({
  name: z.string().min(1),
  birthdate: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  password: z.string().min(8).optional().or(z.literal("")),
});
type ChildForm = z.infer<typeof childSchema>;

export default function SettingsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data: pricing, isLoading: prLoading } = useQuery({
    queryKey: ["pricing-rules"],
    queryFn: () => api.get<PricingRules>("/pricing-rules"),
  });
  const { data: families } = useQuery({
    queryKey: ["families"],
    queryFn: () => api.get<Family[]>("/families"),
    enabled: user?.role === "admin",
  });

  const pricingForm = useForm<PricingForm>({
    resolver: zodResolver(pricingSchema),
    defaultValues: { baby_max_age: 2, kid_max_age: 13 },
  });
  useEffect(() => {
    if (pricing) pricingForm.reset(pricing);
  }, [pricing, pricingForm]);

  const updatePricing = useMutation({
    mutationFn: (v: PricingForm) => api.patch<PricingRules>("/pricing-rules", v),
    onSuccess: () => {
      toast.success(da.profile.saved);
      qc.invalidateQueries({ queryKey: ["pricing-rules"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const familyForm = useForm<FamilyForm>({
    resolver: zodResolver(familySchema),
    defaultValues: { name: "" },
  });

  const [createFamilyOpen, setCreateFamilyOpen] = useState(false);
  const createFamily = useMutation({
    mutationFn: (v: FamilyForm) => api.post<Family>("/families", v),
    onSuccess: () => {
      toast.success("Familie oprettet");
      familyForm.reset();
      setCreateFamilyOpen(false);
      qc.invalidateQueries({ queryKey: ["families"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  // Admins start without a family. We surface a banner with a per-family
  // attach button so they can wire themselves into a family without having
  // to round-trip through the YAML import.
  const { refresh: refreshAuth } = useAuth();
  const attachSelfToFamily = useMutation({
    mutationFn: ({ familyId }: { familyId: number; familyName: string }) =>
      api.patch<User>(`/users/${user?.id}`, { family_id: familyId }),
    onSuccess: async (_data, vars) => {
      toast.success(da.admin.attachedToast(vars.familyName));
      qc.invalidateQueries({ queryKey: ["families"] });
      await refreshAuth();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  if (user?.role !== "admin") {
    return <p className="text-muted-foreground">{da.admin.onlyAdmin}</p>;
  }

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{da.admin.hubTitle}</h1>
        <p className="text-muted-foreground text-sm">{da.admin.hubSubtitle}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{da.admin.pricingTitle}</CardTitle>
          <p className="text-muted-foreground text-sm">
            {da.admin.pricingHint(pricing?.baby_max_age ?? 2, pricing?.kid_max_age ?? 13)}
          </p>
        </CardHeader>
        <CardContent>
          {prLoading || !pricing ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <form
              onSubmit={pricingForm.handleSubmit((v) => updatePricing.mutate(v))}
              className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            >
              <Field>
                <FieldLabel htmlFor="baby">{da.admin.babyMaxAge}</FieldLabel>
                <Input
                  id="baby"
                  type="number"
                  {...pricingForm.register("baby_max_age", { valueAsNumber: true })}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="kid">{da.admin.kidMaxAge}</FieldLabel>
                <Input
                  id="kid"
                  type="number"
                  {...pricingForm.register("kid_max_age", { valueAsNumber: true })}
                />
              </Field>
              <Button type="submit">{da.common.save}</Button>
            </form>
          )}
        </CardContent>
      </Card>

      <ExpenseCategoriesCard />

      <FamilyImportExportCard />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{da.admin.families}</CardTitle>
            <p className="text-muted-foreground text-sm">
              {families ? da.admin.membersCount(families.reduce((n, f) => n + f.members.length, 0)) : ""}
            </p>
          </div>
          <Dialog open={createFamilyOpen} onOpenChange={setCreateFamilyOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="size-4" /> {da.admin.createFamily}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{da.admin.createFamily}</DialogTitle>
              </DialogHeader>
              <form onSubmit={familyForm.handleSubmit((v) => createFamily.mutate(v))}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="fname">{da.admin.familyName}</FieldLabel>
                    <Input id="fname" {...familyForm.register("name")} />
                  </Field>
                  <DialogFooter>
                    <Button type="submit">{da.common.save}</Button>
                  </DialogFooter>
                </FieldGroup>
              </form>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent className="grid gap-3">
          {user.family_id === null && (families?.length ?? 0) > 0 && (
            <div className="bg-amber-100/40 border-amber-400/40 text-amber-900 dark:bg-amber-500/10 dark:text-amber-200 flex items-start gap-3 rounded-lg border p-3 text-sm">
              <AlertTriangle className="size-4 mt-0.5 shrink-0" />
              <p>{da.admin.orphanAdminBanner}</p>
            </div>
          )}
          {families && families.length === 0 && (
            <p className="text-muted-foreground text-sm">{da.admin.noFamilies}</p>
          )}
          {families?.map((f) => (
            <FamilyAdminCard
              key={f.id}
              family={f}
              pricing={pricing}
              currentUserId={user.id}
              currentUserIsOrphanAdmin={user.family_id === null}
              onAttachSelf={() =>
                attachSelfToFamily.mutate({ familyId: f.id, familyName: f.name })
              }
              attachPending={attachSelfToFamily.isPending}
            />
          ))}
        </CardContent>
      </Card>
    </section>
  );
}

function FamilyAdminCard({
  family,
  pricing,
  currentUserId,
  currentUserIsOrphanAdmin,
  onAttachSelf,
  attachPending,
}: {
  family: Family;
  pricing: PricingRules | undefined;
  currentUserId: number;
  currentUserIsOrphanAdmin: boolean;
  onAttachSelf: () => void;
  attachPending: boolean;
}) {
  const qc = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [childOpen, setChildOpen] = useState(false);

  const parents = useMemo(
    () => family.members.filter((m) => m.role !== "child"),
    [family.members],
  );
  const children = useMemo(
    () => family.members.filter((m) => m.role === "child"),
    [family.members],
  );

  const [parentId, setParentId] = useState<string>("");
  useEffect(() => {
    if (parents[0]) setParentId((cur) => cur || String(parents[0].id));
  }, [parents]);

  const inviteForm = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "" },
  });
  const childForm = useForm<ChildForm>({
    resolver: zodResolver(childSchema),
    defaultValues: { name: "", birthdate: "", email: "", password: "" },
  });

  const { data: pendingInvites } = useQuery({
    queryKey: ["invites", family.id],
    queryFn: () => api.get<Invite[]>(`/families/${family.id}/invites`),
  });
  const pending = pendingInvites ?? [];
  const unsentCount = pending.filter((i) => !i.notified_at).length;

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["families"] });
    qc.invalidateQueries({ queryKey: ["invites", family.id] });
  };

  const invite = useMutation({
    mutationFn: (v: InviteForm) =>
      api.post<Invite>(`/families/${family.id}/invites`, { email: v.email, notify: false }),
    onSuccess: () => {
      toast.success(da.family.inviteAddedToast);
      inviteForm.reset({ email: "" });
      setInviteOpen(false);
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const sendAll = useMutation({
    mutationFn: () =>
      api.post<InviteSendResult>(`/families/${family.id}/invites/send-pending`, {}),
    onSuccess: (res) => {
      toast.success(da.family.sentToast(res.sent));
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const cancelInvite = useMutation({
    mutationFn: (id: number) => api.delete<void>(`/families/${family.id}/invites/${id}`),
    onSuccess: () => invalidateAll(),
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "admin" | "parent" }) =>
      api.patch<User>(`/users/${id}/role`, { role }),
    onSuccess: (data) => {
      toast.success(
        data.role === "admin" ? da.family.promotedToast : da.family.demotedToast,
      );
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const deleteUser = useMutation({
    mutationFn: (id: number) => api.delete<void>(`/users/${id}`),
    onSuccess: () => {
      toast.success(da.family.deletedToast);
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const deleteChildMutation = useMutation({
    mutationFn: (id: number) => api.delete<void>(`/children/${id}`),
    onSuccess: () => {
      toast.success(da.family.childDeletedToast);
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const deleteFamily = useMutation({
    mutationFn: () => api.delete<void>(`/families/${family.id}`),
    onSuccess: () => {
      toast.success(da.admin.familyDeletedToast);
      invalidateAll();
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const addChild = useMutation({
    mutationFn: (v: ChildForm) => {
      if (!parentId) throw new Error("missing parent");
      return api.post<User>(`/users/${parentId}/children`, {
        name: v.name,
        birthdate: v.birthdate,
        email: v.email || null,
        password: v.password || null,
      });
    },
    onSuccess: () => {
      toast.success("Barn tilføjet");
      childForm.reset({ name: "", birthdate: "", email: "", password: "" });
      setChildOpen(false);
      qc.invalidateQueries({ queryKey: ["families"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  return (
    <div className="bg-card/50 ring-foreground/10 rounded-xl p-4 ring-1 backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div>
            <p className="text-base font-medium">{family.name}</p>
            <p className="text-muted-foreground text-xs">
              {da.admin.membersCount(family.members.length)}
            </p>
          </div>
          <EditFamilyDialog
            family={family}
            trigger={
              <Button size="icon-sm" variant="ghost" title={da.family.editFamily}>
                <Pencil className="size-4" />
              </Button>
            }
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {currentUserIsOrphanAdmin && (
            <Button
              size="sm"
              variant="default"
              onClick={onAttachSelf}
              disabled={attachPending}
            >
              <Link2 className="size-4" /> {da.admin.attachMe}
            </Button>
          )}
          <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Mail className="size-4" /> {da.family.invite}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {da.family.invite} – {family.name}
                </DialogTitle>
                <DialogDescription>{da.family.pendingNote}</DialogDescription>
              </DialogHeader>
              <form onSubmit={inviteForm.handleSubmit((v) => invite.mutate(v))}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor={`inv-${family.id}`}>{da.auth.email}</FieldLabel>
                    <Input
                      id={`inv-${family.id}`}
                      type="email"
                      {...inviteForm.register("email")}
                    />
                  </Field>
                  <DialogFooter>
                    <Button type="submit">{da.common.save}</Button>
                  </DialogFooter>
                </FieldGroup>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={childOpen} onOpenChange={setChildOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" disabled={parents.length === 0}>
                <Baby className="size-4" /> {da.admin.addChildToFamily}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {da.admin.addChildToFamily} – {family.name}
                </DialogTitle>
                {parents.length === 0 && (
                  <DialogDescription>{da.admin.noParents}</DialogDescription>
                )}
              </DialogHeader>
              <form onSubmit={childForm.handleSubmit((v) => addChild.mutate(v))}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor={`p-${family.id}`}>{da.admin.pickParent}</FieldLabel>
                    <Select value={parentId} onValueChange={setParentId}>
                      <SelectTrigger id={`p-${family.id}`} className="w-full">
                        <SelectValue placeholder={da.admin.pickParent} />
                      </SelectTrigger>
                      <SelectContent>
                        {parents.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor={`cn-${family.id}`}>{da.profile.name}</FieldLabel>
                    <Input id={`cn-${family.id}`} {...childForm.register("name")} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor={`bd-${family.id}`}>{da.profile.birthdate}</FieldLabel>
                    <Input
                      id={`bd-${family.id}`}
                      type="date"
                      {...childForm.register("birthdate")}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor={`ce-${family.id}`}>
                      {da.auth.email} {da.common.optional}
                    </FieldLabel>
                    <Input
                      id={`ce-${family.id}`}
                      type="email"
                      {...childForm.register("email")}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor={`cp-${family.id}`}>
                      {da.auth.password} {da.common.optional}
                    </FieldLabel>
                    <Input
                      id={`cp-${family.id}`}
                      type="password"
                      {...childForm.register("password")}
                    />
                  </Field>
                  <DialogFooter>
                    <Button type="submit" disabled={parents.length === 0}>
                      {da.common.save}
                    </Button>
                  </DialogFooter>
                </FieldGroup>
              </form>
            </DialogContent>
          </Dialog>

          <Button
            size="sm"
            onClick={() => sendAll.mutate()}
            disabled={unsentCount === 0 || sendAll.isPending}
          >
            <Send className="size-4" />
            {da.family.sendAll}
            {unsentCount > 0 && (
              <Badge variant="secondary" className="ml-1">
                {unsentCount}
              </Badge>
            )}
          </Button>

          <ConfirmDialog
            trigger={
              <Button
                size="sm"
                variant="destructive"
                title={da.admin.deleteFamily}
                disabled={deleteFamily.isPending}
              >
                <Trash2 className="size-4" />
                {da.admin.deleteFamily}
              </Button>
            }
            title={da.admin.deleteFamilyConfirmTitle(family.name)}
            description={da.admin.deleteFamilyConfirmBody}
            confirmLabel={da.common.delete}
            onConfirm={() => deleteFamily.mutateAsync()}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MembersColumn
          label={da.admin.parentsLabel}
          icon={<UserPlus className="size-4" />}
        >
          {parents.length === 0 ? (
            <p className="text-muted-foreground text-sm italic">—</p>
          ) : (
            parents.map((m) => (
              <div
                key={m.id}
                className="bg-background/40 ring-foreground/5 flex items-center gap-3 rounded-lg p-2 pr-3 ring-1"
              >
                <Avatar className="size-8">
                  <AvatarFallback>{m.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="text-sm flex-1 min-w-0">
                  <p className="font-medium flex items-center gap-2">
                    {m.name}
                    {m.role === "admin" && (
                      <Badge variant="default" className="gap-1">
                        <ShieldCheck className="size-3" />
                        {da.family.adminBadge}
                      </Badge>
                    )}
                  </p>
                  <p className="text-muted-foreground text-xs truncate">{m.email ?? "—"}</p>
                </div>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  title={m.role === "admin" ? da.family.demoteAdmin : da.family.promoteAdmin}
                  disabled={
                    setRole.isPending ||
                    (m.role === "admin" && m.id === currentUserId)
                  }
                  onClick={() =>
                    setRole.mutate({
                      id: m.id,
                      role: m.role === "admin" ? "parent" : "admin",
                    })
                  }
                >
                  {m.role === "admin" ? (
                    <Shield className="size-4" />
                  ) : (
                    <ShieldCheck className="size-4" />
                  )}
                </Button>
                <ConfirmDialog
                  trigger={
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title={da.family.deleteParent}
                      disabled={deleteUser.isPending || m.id === currentUserId}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  }
                  title={da.family.deleteParentConfirmTitle(m.name)}
                  description={da.family.deleteParentConfirmBody}
                  confirmLabel={da.common.delete}
                  onConfirm={() => deleteUser.mutateAsync(m.id)}
                />
              </div>
            ))
          )}

          {pending.length > 0 && (
            <div className="mt-2 grid gap-2">
              <p className="text-muted-foreground text-xs uppercase tracking-wide">
                {da.family.pendingInvitations}
              </p>
              {pending.map((inv) => (
                <div
                  key={inv.id}
                  className="bg-background/30 ring-foreground/5 flex items-center gap-3 rounded-lg p-2 pr-3 ring-1"
                >
                  <div className="bg-amber-400/20 text-amber-600 dark:text-amber-300 size-8 rounded-full grid place-items-center">
                    <Mail className="size-4" />
                  </div>
                  <div className="text-sm flex-1 min-w-0">
                    <p className="font-medium truncate">{inv.email}</p>
                    <p className="text-muted-foreground text-xs">
                      {inv.notified_at
                        ? da.family.notifiedAt(inv.notified_at)
                        : da.family.notNotified}
                    </p>
                  </div>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    title={da.family.cancelInvite}
                    onClick={() => cancelInvite.mutate(inv.id)}
                    disabled={cancelInvite.isPending}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </MembersColumn>

        <MembersColumn
          label={da.admin.childrenLabel}
          icon={<Baby className="size-4" />}
        >
          {children.length === 0 ? (
            <p className="text-muted-foreground text-sm italic">—</p>
          ) : (
            children.map((m) => {
              const cat = classifyAge(ageOn(m.birthdate), pricing);
              return (
                <div
                  key={m.id}
                  className="bg-background/40 ring-foreground/5 flex items-center gap-3 rounded-lg p-2 pr-3 ring-1"
                >
                  <Avatar className="size-8">
                    <AvatarFallback>{m.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <div className="text-sm flex-1 min-w-0">
                    <p className="font-medium">{m.name}</p>
                    <p className="text-muted-foreground text-xs">
                      {m.birthdate ? `f. ${m.birthdate}` : "—"}
                    </p>
                  </div>
                  {cat !== "unknown" && (
                    <Badge variant={categoryVariant(cat)}>{categoryLabel(cat)}</Badge>
                  )}
                  <EditChildDialog
                    user={m}
                    trigger={
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title={da.family.editChild}
                      >
                        <Pencil className="size-4" />
                      </Button>
                    }
                  />
                  <ConfirmDialog
                    trigger={
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        title={da.family.deleteChild}
                        disabled={deleteChildMutation.isPending}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    }
                    title={da.family.deleteChildConfirmTitle(m.name)}
                    description={da.family.deleteChildConfirmBody}
                    confirmLabel={da.common.delete}
                    onConfirm={() => deleteChildMutation.mutateAsync(m.id)}
                  />
                </div>
              );
            })
          )}
        </MembersColumn>
      </div>
    </div>
  );
}

const categorySchema = z.object({
  name: z.string().min(1),
  is_per_person: z.boolean().default(false),
  is_per_night: z.boolean().default(false),
  is_utility: z.boolean().default(false),
});
type CategoryForm = z.infer<typeof categorySchema>;
type CategoryFormInput = z.input<typeof categorySchema>;

function ExpenseCategoriesCard() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: categories } = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => api.get<ExpenseCategory[]>("/expense-categories"),
  });

  const form = useForm<CategoryFormInput, unknown, CategoryForm>({
    resolver: zodResolver(categorySchema),
    defaultValues: {
      name: "",
      is_per_person: false,
      is_per_night: false,
      is_utility: false,
    },
  });

  const create = useMutation({
    mutationFn: (v: CategoryForm) => api.post<ExpenseCategory>("/expense-categories", v),
    onSuccess: () => {
      toast.success(da.expenseCategories.saved);
      setOpen(false);
      form.reset({
        name: "",
        is_per_person: false,
        is_per_night: false,
        is_utility: false,
      });
      qc.invalidateQueries({ queryKey: ["expense-categories"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<CategoryForm> }) =>
      api.patch<ExpenseCategory>(`/expense-categories/${id}`, body),
    onSuccess: () => {
      toast.success(da.expenseCategories.saved);
      qc.invalidateQueries({ queryKey: ["expense-categories"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/expense-categories/${id}`),
    onSuccess: () => {
      toast.success(da.expenseCategories.deleted);
      qc.invalidateQueries({ queryKey: ["expense-categories"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{da.expenseCategories.title}</CardTitle>
          <p className="text-muted-foreground text-sm">{da.expenseCategories.subtitle}</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="size-4" /> {da.expenseCategories.add}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{da.expenseCategories.add}</DialogTitle>
            </DialogHeader>
            <form onSubmit={form.handleSubmit((v) => create.mutate(v))}>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="cat-name">{da.expenseCategories.name}</FieldLabel>
                  <Input id="cat-name" {...form.register("name")} />
                </Field>
                <CategoryFlagRow
                  label={da.expenseCategories.perPerson}
                  checked={form.watch("is_per_person") ?? false}
                  onChange={(v) => form.setValue("is_per_person", v)}
                />
                <CategoryFlagRow
                  label={da.expenseCategories.perNight}
                  checked={form.watch("is_per_night") ?? false}
                  onChange={(v) => form.setValue("is_per_night", v)}
                />
                <CategoryFlagRow
                  label={da.expenseCategories.utility}
                  checked={form.watch("is_utility") ?? false}
                  onChange={(v) => form.setValue("is_utility", v)}
                />
                <DialogFooter>
                  <Button type="submit" disabled={create.isPending}>
                    {da.common.save}
                  </Button>
                </DialogFooter>
              </FieldGroup>
            </form>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="grid gap-2">
        {(categories ?? []).map((c) => (
          <div
            key={c.id}
            className="bg-background/40 ring-foreground/5 grid gap-2 rounded-lg p-3 ring-1 sm:grid-cols-[2fr_3fr_auto] sm:items-center"
          >
            <p className="font-medium">{c.name}</p>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <CategoryFlagRow
                label={da.expenseCategories.perPerson}
                checked={c.is_per_person}
                onChange={(v) => update.mutate({ id: c.id, body: { is_per_person: v } })}
              />
              <CategoryFlagRow
                label={da.expenseCategories.perNight}
                checked={c.is_per_night}
                onChange={(v) => update.mutate({ id: c.id, body: { is_per_night: v } })}
              />
              <CategoryFlagRow
                label={da.expenseCategories.utility}
                checked={c.is_utility}
                onChange={(v) => update.mutate({ id: c.id, body: { is_utility: v } })}
              />
            </div>
            <ConfirmDialog
              trigger={
                <Button size="icon-sm" variant="ghost" title={da.common.delete}>
                  <Trash2 className="size-4" />
                </Button>
              }
              title={da.expenseCategories.deleteConfirm}
              description={`${c.name}`}
              confirmLabel={da.common.delete}
              onConfirm={() => remove.mutateAsync(c.id)}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function CategoryFlagRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <Switch checked={checked} onCheckedChange={onChange} />
      <span>{label}</span>
    </label>
  );
}

function MembersColumn({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-2 content-start">
      <p className="text-muted-foreground flex items-center gap-2 text-xs uppercase tracking-wide">
        {icon}
        {label}
      </p>
      {children}
    </div>
  );
}

type ImportSummaryDto = {
  families_created: number;
  parents_created: number;
  children_created: number;
  parents_attached: number;
  skipped: { families: number; parents: number; children: number };
};

function FamilyImportExportCard() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [exporting, setExporting] = useState(false);

  const importYaml = useMutation({
    mutationFn: (yamlPayload: string) =>
      api.post<ImportSummaryDto>("/admin/families/import", { yaml: yamlPayload }),
    onSuccess: (summary) => {
      toast.success(
        `${da.admin.importedToast}: ${da.admin.importSummary({
          families: summary.families_created,
          parents: summary.parents_created,
          children: summary.children_created,
          parentsAttached: summary.parents_attached,
        })}`,
      );
      setYamlText("");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["families"] });
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  const exportYaml = async () => {
    setExporting(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
      const res = await fetch(`${base}/admin/families/export`, {
        credentials: "include",
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        let detail = res.statusText;
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          if (parsed.detail) detail = parsed.detail;
        } catch {
          if (text) detail = text;
        }
        throw new ApiError(res.status, `${res.status} ${detail}`, null);
      }
      const text = await res.text();
      const blob = new Blob([text], { type: "application/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = da.admin.exportFilename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(da.admin.exportedToast);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error(String(e));
    } finally {
      setExporting(false);
    }
  };

  const onPickFile = (file: File | null | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") setYamlText(result);
    };
    reader.readAsText(file);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{da.admin.importExportTitle}</CardTitle>
        <p className="text-muted-foreground text-sm">{da.admin.importExportHint}</p>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button onClick={exportYaml} disabled={exporting} variant="outline">
          <Download className="size-4" /> {da.admin.exportButton}
        </Button>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="outline">
              <Upload className="size-4" /> {da.admin.importButton}
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>{da.admin.importDialogTitle}</DialogTitle>
              <DialogDescription>{da.admin.importDialogBody}</DialogDescription>
            </DialogHeader>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="yaml-file">{da.admin.importFromFile}</FieldLabel>
                <Input
                  id="yaml-file"
                  type="file"
                  accept=".yaml,.yml,text/yaml,application/yaml"
                  onChange={(e) => onPickFile(e.target.files?.[0])}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="yaml-text">YAML</FieldLabel>
                <Textarea
                  id="yaml-text"
                  rows={14}
                  spellCheck={false}
                  className="font-mono text-xs"
                  placeholder={da.admin.importPlaceholder}
                  value={yamlText}
                  onChange={(e) => setYamlText(e.target.value)}
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button
                onClick={() => importYaml.mutate(yamlText)}
                disabled={!yamlText.trim() || importYaml.isPending}
              >
                {da.admin.importSubmit}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
