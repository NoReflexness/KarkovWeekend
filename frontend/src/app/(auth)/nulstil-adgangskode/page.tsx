"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { da } from "@/i18n/da";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const schema = z.object({
  token: z.string().min(8),
  new_password: z.string().min(8),
});
type FormValues = z.infer<typeof schema>;

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const tokenFromUrl = params.get("token") ?? "";
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { token: tokenFromUrl, new_password: "" },
  });

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", values);
      toast.success("Adgangskode nulstillet. Log ind igen.");
      router.push("/login");
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
        <CardTitle>{da.auth.resetTitle}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="token">Token</FieldLabel>
              <Input id="token" {...form.register("token")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="new_password">{da.auth.newPassword}</FieldLabel>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...form.register("new_password")}
              />
            </Field>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? da.common.loading : da.auth.resetCta}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ResetForm />
    </Suspense>
  );
}
