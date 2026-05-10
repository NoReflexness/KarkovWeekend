"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const schema = z.object({
  token: z.string().min(8, "Token mangler"),
  name: z.string().min(1, "Påkrævet"),
  password: z.string().min(8, "Mindst 8 tegn"),
  birthdate: z.string().optional().or(z.literal("")),
});
type FormValues = z.infer<typeof schema>;

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const tokenFromUrl = params.get("token") ?? "";
  const { refresh } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { token: tokenFromUrl, name: "", password: "", birthdate: "" },
  });

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    try {
      await api.post("/auth/register", {
        token: values.token,
        name: values.name,
        password: values.password,
        birthdate: values.birthdate || null,
      });
      await refresh();
      toast.success("Velkommen!");
      router.push("/");
    } catch (e) {
      if (e instanceof ApiError) {
        toast.error(e.message);
      } else {
        toast.error(da.common.error);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{da.auth.registerTitle}</CardTitle>
        <CardDescription>{da.auth.inviteHint}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field data-invalid={!!form.formState.errors.token}>
              <FieldLabel htmlFor="token">Invitations-token</FieldLabel>
              <Input id="token" {...form.register("token")} />
            </Field>
            <Field data-invalid={!!form.formState.errors.name}>
              <FieldLabel htmlFor="name">{da.auth.name}</FieldLabel>
              <Input id="name" autoComplete="name" {...form.register("name")} />
              {form.formState.errors.name && (
                <FieldDescription>{form.formState.errors.name.message}</FieldDescription>
              )}
            </Field>
            <Field data-invalid={!!form.formState.errors.password}>
              <FieldLabel htmlFor="password">{da.auth.password}</FieldLabel>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <FieldDescription>{form.formState.errors.password.message}</FieldDescription>
              )}
            </Field>
            <Field>
              <FieldLabel htmlFor="birthdate">
                {da.auth.birthdate} {da.common.optional}
              </FieldLabel>
              <Input id="birthdate" type="date" {...form.register("birthdate")} />
            </Field>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? da.common.loading : da.auth.registerCta}
            </Button>
            <Link
              href="/login"
              className="text-muted-foreground hover:underline text-sm"
            >
              {da.auth.loginCta}
            </Link>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <RegisterForm />
    </Suspense>
  );
}
