"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { da } from "@/i18n/da";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const schema = z.object({
  email: z.string().email("Ugyldig email"),
  password: z.string().min(1, "Påkrævet"),
});
type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/";
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    try {
      await login(values.email, values.password);
      router.push(next);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        form.setError("password", { message: da.auth.invalidCredentials });
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
        <CardTitle>{da.auth.loginTitle}</CardTitle>
        <CardDescription>{da.app.tagline}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field data-invalid={!!form.formState.errors.email}>
              <FieldLabel htmlFor="email">{da.auth.email}</FieldLabel>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                aria-invalid={!!form.formState.errors.email}
                {...form.register("email")}
              />
              {form.formState.errors.email && (
                <FieldDescription>{form.formState.errors.email.message}</FieldDescription>
              )}
            </Field>
            <Field data-invalid={!!form.formState.errors.password}>
              <FieldLabel htmlFor="password">{da.auth.password}</FieldLabel>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!form.formState.errors.password}
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <FieldDescription>{form.formState.errors.password.message}</FieldDescription>
              )}
            </Field>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? da.common.loading : da.auth.loginCta}
            </Button>
            <div className="text-muted-foreground flex flex-col gap-2 text-sm">
              <Link href="/glemt-adgangskode" className="hover:underline">
                {da.auth.forgot}
              </Link>
              <p>{da.auth.needAccount}</p>
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <LoginForm />
    </Suspense>
  );
}
