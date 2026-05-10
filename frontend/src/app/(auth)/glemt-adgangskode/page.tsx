"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { da } from "@/i18n/da";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const schema = z.object({ email: z.string().email() });
type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    try {
      await api.post("/auth/forgot-password", values);
      toast.success(da.auth.forgotSent);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{da.auth.forgotTitle}</CardTitle>
        <CardDescription>{da.auth.forgotSent}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="email">{da.auth.email}</FieldLabel>
              <Input id="email" type="email" {...form.register("email")} />
            </Field>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? da.common.loading : da.auth.forgotCta}
            </Button>
            <Link href="/login" className="text-muted-foreground text-sm hover:underline">
              {da.auth.loginCta}
            </Link>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
