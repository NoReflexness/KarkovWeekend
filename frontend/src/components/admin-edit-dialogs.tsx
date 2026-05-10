"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { da } from "@/i18n/da";
import type { Family, User } from "@/lib/types";

import { Button } from "@/components/ui/button";
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

const userEditSchema = z.object({
  name: z.string().min(1).max(120),
  birthdate: z.string().optional().or(z.literal("")),
  email: z.string().email().optional().or(z.literal("")),
  password: z.string().min(8).max(128).optional().or(z.literal("")),
});
type UserEditForm = z.infer<typeof userEditSchema>;

interface UserDialogProps {
  user: User;
  trigger: React.ReactNode;
  onSaved?: () => void;
  /** Endpoint to PATCH. Defaults to admin's /users/{id}. Override to /children/{id} for children. */
  endpoint?: string;
  title?: string;
}

function UserEditDialog({ user, trigger, onSaved, endpoint, title }: UserDialogProps) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const form = useForm<UserEditForm>({
    resolver: zodResolver(userEditSchema),
    defaultValues: {
      name: user.name,
      birthdate: user.birthdate ?? "",
      email: user.email ?? "",
      password: "",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: user.name,
        birthdate: user.birthdate ?? "",
        email: user.email ?? "",
        password: "",
      });
    }
  }, [open, user, form]);

  const url = endpoint ?? `/users/${user.id}`;
  const save = useMutation({
    mutationFn: (v: UserEditForm) => {
      const body: Record<string, unknown> = { name: v.name };
      if (v.birthdate) body.birthdate = v.birthdate;
      if (v.email) body.email = v.email;
      if (v.password) body.password = v.password;
      return api.patch<User>(url, body);
    },
    onSuccess: () => {
      toast.success(da.family.updatedToast);
      qc.invalidateQueries({ queryKey: ["families"] });
      onSaved?.();
      setOpen(false);
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title ?? da.family.editParentTitle(user.name)}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => save.mutate(v))}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor={`u-name-${user.id}`}>{da.profile.name}</FieldLabel>
              <Input id={`u-name-${user.id}`} {...form.register("name")} />
            </Field>
            <Field>
              <FieldLabel htmlFor={`u-bd-${user.id}`}>{da.profile.birthdate}</FieldLabel>
              <Input
                id={`u-bd-${user.id}`}
                type="date"
                {...form.register("birthdate")}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor={`u-email-${user.id}`}>{da.auth.email}</FieldLabel>
              <Input
                id={`u-email-${user.id}`}
                type="email"
                {...form.register("email")}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor={`u-pw-${user.id}`}>
                {da.auth.password} <span className="text-muted-foreground text-xs">({da.family.passwordHint})</span>
              </FieldLabel>
              <Input
                id={`u-pw-${user.id}`}
                type="password"
                autoComplete="new-password"
                {...form.register("password")}
              />
            </Field>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={save.isPending}
              >
                {da.common.cancel}
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {da.common.save}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function EditParentDialog(props: Omit<UserDialogProps, "endpoint" | "title">) {
  return (
    <UserEditDialog
      {...props}
      endpoint={`/users/${props.user.id}`}
      title={da.family.editParentTitle(props.user.name)}
    />
  );
}

export function EditChildDialog(props: Omit<UserDialogProps, "endpoint" | "title">) {
  return (
    <UserEditDialog
      {...props}
      endpoint={`/children/${props.user.id}`}
      title={da.family.editChildTitle(props.user.name)}
    />
  );
}

const familySchema = z.object({ name: z.string().min(1).max(120) });
type FamilyForm = z.infer<typeof familySchema>;

export function EditFamilyDialog({
  family,
  trigger,
  onSaved,
}: {
  family: Family;
  trigger: React.ReactNode;
  onSaved?: () => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useForm<FamilyForm>({
    resolver: zodResolver(familySchema),
    defaultValues: { name: family.name },
  });

  useEffect(() => {
    if (open) form.reset({ name: family.name });
  }, [open, family, form]);

  const save = useMutation({
    mutationFn: (v: FamilyForm) => api.patch<Family>(`/families/${family.id}`, v),
    onSuccess: () => {
      toast.success(da.family.updatedToast);
      qc.invalidateQueries({ queryKey: ["families"] });
      onSaved?.();
      setOpen(false);
    },
    onError: (e) => e instanceof ApiError && toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{da.family.editFamilyTitle(family.name)}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => save.mutate(v))}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor={`f-name-${family.id}`}>{da.admin.familyName}</FieldLabel>
              <Input id={`f-name-${family.id}`} {...form.register("name")} />
            </Field>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={save.isPending}
              >
                {da.common.cancel}
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {da.common.save}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}
