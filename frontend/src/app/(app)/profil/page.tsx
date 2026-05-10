"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Bell, BellOff, Pencil, Users, Baby } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { publicUrl } from "@/lib/format";
import type { Family, NotifyPref, User } from "@/lib/types";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  EditChildDialog,
  EditParentDialog,
} from "@/components/admin-edit-dialogs";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const profileSchema = z.object({
  name: z.string().min(1),
  birthdate: z.string().optional(),
});
type ProfileForm = z.infer<typeof profileSchema>;

const passwordSchema = z.object({
  current_password: z.string().min(1),
  new_password: z.string().min(8),
});
type PasswordForm = z.infer<typeof passwordSchema>;

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [savingPic, setSavingPic] = useState(false);

  const { data: notifyPref } = useQuery({
    queryKey: ["notify-pref"],
    queryFn: () => api.get<NotifyPref>("/chat/notify-pref"),
  });

  const setNotify = useMutation({
    mutationFn: (notify_email: boolean) =>
      api.put<NotifyPref>("/chat/notify-pref", { notify_email }),
    onSuccess: () => {
      toast.success(da.notify.savedToast);
      qc.invalidateQueries({ queryKey: ["notify-pref"] });
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user?.name ?? "", birthdate: user?.birthdate ?? "" },
    values: { name: user?.name ?? "", birthdate: user?.birthdate ?? "" },
  });
  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "" },
  });

  if (!user) return <Skeleton className="h-64 w-full" />;

  const saveProfile = async (v: ProfileForm) => {
    try {
      await api.patch("/me", {
        name: v.name,
        birthdate: v.birthdate || null,
      });
      await refresh();
      toast.success(da.profile.saved);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  };

  const changePassword = async (v: PasswordForm) => {
    try {
      await api.post("/me/change-password", v);
      passwordForm.reset();
      toast.success(da.profile.saved);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  };

  const uploadPicture = async (file: File) => {
    setSavingPic(true);
    try {
      await api.upload<User>("/me/profile-picture", file);
      await refresh();
      toast.success(da.profile.saved);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setSavingPic(false);
    }
  };

  return (
    <section className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{da.profile.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <Avatar className="size-20">
              {user.profile_picture_url && (
                <AvatarImage src={publicUrl(user.profile_picture_url)} alt={user.name} />
              )}
              <AvatarFallback>{user.name.slice(0, 2).toUpperCase()}</AvatarFallback>
            </Avatar>
            <div className="flex flex-col gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => e.target.files?.[0] && uploadPicture(e.target.files[0])}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileRef.current?.click()}
                disabled={savingPic}
              >
                {savingPic ? da.common.loading : da.profile.uploadPicture}
              </Button>
            </div>
          </div>

          <form onSubmit={profileForm.handleSubmit(saveProfile)}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="pname">{da.profile.name}</FieldLabel>
                <Input id="pname" {...profileForm.register("name")} />
              </Field>
              <Field>
                <FieldLabel htmlFor="pemail">{da.profile.email}</FieldLabel>
                <Input id="pemail" value={user.email ?? ""} disabled readOnly />
              </Field>
              <Field>
                <FieldLabel htmlFor="pbd">{da.profile.birthdate}</FieldLabel>
                <Input id="pbd" type="date" {...profileForm.register("birthdate")} />
              </Field>
              <Button type="submit">{da.profile.save}</Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" />
            {da.profile.notificationsTitle}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-muted-foreground text-sm">{da.profile.notificationsHint}</p>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground text-xs uppercase tracking-wide">
              {notifyPref?.notify_email == null
                ? da.profile.notifyEmailUnset
                : notifyPref.notify_email
                  ? "Email: ON"
                  : "Email: OFF"}
            </span>
            <Button
              size="sm"
              variant={notifyPref?.notify_email ? "secondary" : "default"}
              onClick={() => setNotify.mutate(true)}
              disabled={setNotify.isPending || notifyPref?.notify_email === true}
            >
              <Bell className="size-4" />
              {da.profile.notifyEmailOn}
            </Button>
            <Button
              size="sm"
              variant={notifyPref?.notify_email === false ? "secondary" : "outline"}
              onClick={() => setNotify.mutate(false)}
              disabled={setNotify.isPending || notifyPref?.notify_email === false}
            >
              <BellOff className="size-4" />
              {da.profile.notifyEmailOff}
            </Button>
          </div>
        </CardContent>
      </Card>

      <FamilyMembersCard currentUserId={user.id} familyId={user.family_id} />

      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>{da.profile.changePassword}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={passwordForm.handleSubmit(changePassword)}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="cur-pw">{da.profile.currentPassword}</FieldLabel>
                <Input
                  id="cur-pw"
                  type="password"
                  autoComplete="current-password"
                  {...passwordForm.register("current_password")}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="new-pw">{da.profile.newPassword}</FieldLabel>
                <Input
                  id="new-pw"
                  type="password"
                  autoComplete="new-password"
                  {...passwordForm.register("new_password")}
                />
              </Field>
              <Button type="submit">{da.profile.save}</Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}

function FamilyMembersCard({
  currentUserId,
  familyId,
}: {
  currentUserId: number;
  familyId: number | null;
}) {
  const { data: family, isLoading } = useQuery({
    queryKey: ["family", familyId],
    queryFn: () => api.get<Family>(`/families/${familyId}`),
    enabled: familyId !== null,
  });

  return (
    <Card className="md:col-span-2">
      <CardHeader>
        <CardTitle>{da.profile.familyTitle}</CardTitle>
        <p className="text-muted-foreground text-sm">{da.profile.familyHint}</p>
      </CardHeader>
      <CardContent className="grid gap-4">
        {familyId === null && (
          <p className="text-muted-foreground text-sm">{da.profile.noFamily}</p>
        )}
        {isLoading && <Skeleton className="h-20 w-full" />}
        {family && (
          <div className="grid gap-4 sm:grid-cols-2">
            <FamilyColumn
              icon={<Users className="size-4" />}
              label={da.profile.membersHeading}
              members={family.members.filter((m) => m.role !== "child")}
              renderEdit={(member) =>
                member.id === currentUserId ? null : (
                  <EditParentDialog
                    user={member}
                    trigger={
                      <Button
                        size="icon"
                        variant="ghost"
                        title={da.family.editParent}
                      >
                        <Pencil className="size-4" />
                      </Button>
                    }
                  />
                )
              }
            />
            <FamilyColumn
              icon={<Baby className="size-4" />}
              label={da.profile.childrenHeading}
              members={family.members.filter((m) => m.role === "child")}
              renderEdit={(member) => (
                <EditChildDialog
                  user={member}
                  trigger={
                    <Button
                      size="icon"
                      variant="ghost"
                      title={da.family.editChild}
                    >
                      <Pencil className="size-4" />
                    </Button>
                  }
                />
              )}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FamilyColumn({
  icon,
  label,
  members,
  renderEdit,
}: {
  icon: React.ReactNode;
  label: string;
  members: User[];
  renderEdit: (m: User) => React.ReactNode;
}) {
  return (
    <div className="grid gap-2 content-start">
      <p className="text-muted-foreground flex items-center gap-2 text-xs uppercase tracking-wide">
        {icon}
        {label}
      </p>
      {members.length === 0 && (
        <p className="text-muted-foreground text-xs">—</p>
      )}
      {members.map((m) => (
        <div
          key={m.id}
          className="flex items-center gap-2 rounded-md border px-3 py-2"
        >
          <Avatar className="size-7">
            {m.profile_picture_url && (
              <AvatarImage src={publicUrl(m.profile_picture_url)} alt={m.name} />
            )}
            <AvatarFallback>{m.name.slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div className="flex flex-col flex-1 min-w-0">
            <span className="truncate text-sm font-medium">{m.name}</span>
            {m.email && (
              <span className="truncate text-muted-foreground text-xs">
                {m.email}
              </span>
            )}
          </div>
          {renderEdit(m)}
        </div>
      ))}
    </div>
  );
}
