"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatKr } from "@/lib/format";
import type {
  Budget,
  Expense,
  ExpenseCategory,
  KarkovEvent,
  User,
} from "@/lib/types";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

const NO_CHOR = "__none__";

const schema = z.object({
  category_id: z.string().min(1),
  amount_kr: z.string().min(1),
  description: z.string().optional(),
  chor_id: z.string().optional(),
  paid_by_user_id: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

const MEAL_LABELS: Record<string, string> = {
  morgenmad: "Morgenmad",
  frokost: "Frokost",
  aftensmad: "Aftensmad",
};
const ACTION_LABELS: Record<string, string> = {
  forberedelse: "Forberedelse",
  oprydning: "Oprydning",
};

export function BudgetTab({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const isChild = user?.role === "child";
  const isAdmin = user?.role === "admin";

  // Always declare hooks unconditionally; gate the render at the bottom.
  const { data: budget, isLoading: budgetLoading } = useQuery({
    queryKey: ["budget", event.id],
    queryFn: () => api.get<Budget>(`/events/${event.id}/budget`),
    enabled: !isChild,
  });
  const { data: categories } = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => api.get<ExpenseCategory[]>("/expense-categories"),
    enabled: !isChild,
  });
  const { data: expenses } = useQuery({
    queryKey: ["expenses", event.id],
    queryFn: () => api.get<Expense[]>(`/events/${event.id}/expenses`),
    enabled: !isChild,
  });
  const { data: payerCandidates } = useQuery({
    queryKey: ["users", "payers"],
    queryFn: () => api.get<User[]>("/users"),
    enabled: isAdmin,
  });
  const payers = useMemo(
    () => (payerCandidates ?? []).filter((u) => u.role !== "child"),
    [payerCandidates],
  );
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      category_id: "",
      amount_kr: "",
      description: "",
      chor_id: NO_CHOR,
    },
  });
  const editForm = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      category_id: "",
      amount_kr: "",
      description: "",
      chor_id: NO_CHOR,
      paid_by_user_id: "",
    },
  });

  const invalidateBudget = () => {
    qc.invalidateQueries({ queryKey: ["budget", event.id] });
    qc.invalidateQueries({ queryKey: ["expenses", event.id] });
  };

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.post(`/events/${event.id}/expenses`, {
        category_id: Number(v.category_id),
        amount_cents: Math.round(parseFloat(v.amount_kr.replace(",", ".")) * 100),
        description: v.description || null,
        chor_id: v.chor_id && v.chor_id !== NO_CHOR ? Number(v.chor_id) : null,
      }),
    onSuccess: () => {
      toast.success("Udgift tilføjet");
      setOpen(false);
      form.reset({ category_id: "", amount_kr: "", description: "", chor_id: NO_CHOR });
      invalidateBudget();
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const update = useMutation({
    mutationFn: ({ id, v }: { id: number; v: FormValues }) =>
      api.patch(`/expenses/${id}`, {
        category_id: Number(v.category_id),
        amount_cents: Math.round(parseFloat(v.amount_kr.replace(",", ".")) * 100),
        description: v.description || null,
        chor_id: v.chor_id && v.chor_id !== NO_CHOR ? Number(v.chor_id) : null,
        // Only send paid_by_user_id when admin actually changed it.
        paid_by_user_id:
          isAdmin && v.paid_by_user_id ? Number(v.paid_by_user_id) : undefined,
      }),
    onSuccess: () => {
      toast.success(da.budget.expenseUpdatedToast);
      setEditingId(null);
      invalidateBudget();
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/expenses/${id}`),
    onSuccess: () => invalidateBudget(),
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
    },
  });

  const beginEdit = (e: Expense) => {
    editForm.reset({
      category_id: String(e.category_id),
      amount_kr: (e.amount_cents / 100).toFixed(2).replace(".", ","),
      description: e.description ?? "",
      chor_id: e.chor_id ? String(e.chor_id) : NO_CHOR,
      paid_by_user_id: String(e.paid_by_user_id),
    });
    setEditingId(e.id);
  };

  const familyName = (id: number) =>
    budget?.family_names?.[id] ?? `Familie ${id}`;

  const flatChors = useMemo(() => {
    return event.days.flatMap((d) =>
      d.chors.map((c) => ({
        id: c.id,
        date: d.date,
        meal: c.meal as string,
        action: c.action as string,
      })),
    );
  }, [event.days]);

  const utilityPendingNames = useMemo(() => {
    const cats = categories ?? [];
    const exp = expenses ?? [];
    return cats
      .filter((c) => c.is_utility)
      .filter((c) => !exp.some((e) => e.category_id === c.id))
      .map((c) => c.name);
  }, [categories, expenses]);

  const perFamily = useMemo(() => {
    if (!budget) return [];
    const totals = new Map<
      number,
      { paid_cents: number; share_cents: number; net_cents: number }
    >();
    for (const s of budget.shares) {
      const t = totals.get(s.family_id) ?? {
        paid_cents: 0,
        share_cents: 0,
        net_cents: 0,
      };
      t.paid_cents += s.paid_cents;
      t.share_cents += s.share_cents;
      t.net_cents += s.net_cents;
      totals.set(s.family_id, t);
    }
    return Array.from(totals.entries())
      .map(([family_id, t]) => ({ family_id, ...t }))
      .sort((a, b) => a.family_id - b.family_id);
  }, [budget]);

  if (isChild) {
    return (
      <Alert>
        <AlertTitle>Kun for voksne</AlertTitle>
        <AlertDescription>Børn kan ikke se budgettet.</AlertDescription>
      </Alert>
    );
  }

  const isFinal = budget?.is_final ?? false;
  const myFamilyId = user?.family_id;
  const myShare = budget?.shares.find((s) => s.family_id === myFamilyId);
  const canAdd = isAdmin || !isFinal;
  const canMutate = (e: Expense) =>
    isAdmin || (e.paid_by_user_id === user?.id && !isFinal);
  const editing = expenses?.find((e) => e.id === editingId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      {isFinal && (
        <Alert>
          <AlertTitle>
            {isAdmin ? da.budget.lockedAdminOverride : da.budget.locked}
          </AlertTitle>
        </Alert>
      )}

      {!isFinal && utilityPendingNames.length > 0 && (
        <Alert>
          <AlertTitle>{da.budget.utilitiesPendingTitle}</AlertTitle>
          <AlertDescription>
            {da.budget.utilitiesPendingBody(utilityPendingNames.join(", "))}
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-base">{da.budget.total}</CardTitle>
          {canAdd && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="size-4" /> {da.budget.addExpense}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{da.budget.addExpense}</DialogTitle>
                </DialogHeader>
                <form onSubmit={form.handleSubmit((v) => create.mutate(v))}>
                  <FieldGroup>
                    <Field>
                      <FieldLabel htmlFor="category">{da.budget.category}</FieldLabel>
                      <Select
                        value={form.watch("category_id")}
                        onValueChange={(v) => form.setValue("category_id", v)}
                      >
                        <SelectTrigger id="category">
                          <SelectValue placeholder="Vælg kategori" />
                        </SelectTrigger>
                        <SelectContent>
                          {categories?.map((c) => (
                            <SelectItem key={c.id} value={String(c.id)}>
                              {c.name}
                              {c.is_utility ? " · forbrug" : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="amount">{da.budget.amount}</FieldLabel>
                      <Input
                        id="amount"
                        inputMode="decimal"
                        placeholder="0,00"
                        {...form.register("amount_kr")}
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="desc">{da.budget.description}</FieldLabel>
                      <Input id="desc" {...form.register("description")} />
                    </Field>
                    {flatChors.length > 0 && (
                      <Field>
                        <FieldLabel htmlFor="chor">
                          {da.budget.chor}{" "}
                          <span className="text-muted-foreground text-xs">
                            {da.budget.chorOptional}
                          </span>
                        </FieldLabel>
                        <Select
                          value={form.watch("chor_id") ?? NO_CHOR}
                          onValueChange={(v) => form.setValue("chor_id", v)}
                        >
                          <SelectTrigger id="chor" className="w-full">
                            <SelectValue placeholder={da.budget.chorNone} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={NO_CHOR}>{da.budget.chorNone}</SelectItem>
                            {flatChors.map((c) => (
                              <SelectItem key={c.id} value={String(c.id)}>
                                {c.date} · {MEAL_LABELS[c.meal] ?? c.meal} ·{" "}
                                {ACTION_LABELS[c.action] ?? c.action}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Field>
                    )}
                    <DialogFooter>
                      <Button type="submit">{da.common.save}</Button>
                    </DialogFooter>
                  </FieldGroup>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </CardHeader>
        <CardContent>
          {budgetLoading || !budget ? (
            <Skeleton className="h-16 w-32" />
          ) : (
            <>
              <p className="text-3xl font-semibold">
                {formatKr(budget.total_cents)} {da.common.danishCurrency}
              </p>
              {myShare && (
                <div className="text-muted-foreground mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div>
                    <p>{da.budget.yourShare}</p>
                    <p className="text-foreground font-medium">
                      {formatKr(myShare.share_cents)}
                    </p>
                  </div>
                  <div>
                    <p>{da.budget.youPaid}</p>
                    <p className="text-foreground font-medium">
                      {formatKr(myShare.paid_cents)}
                    </p>
                  </div>
                  <div className="col-span-2 sm:col-span-2">
                    <p>{da.budget.net}</p>
                    <p
                      className={
                        myShare.net_cents > 0
                          ? "font-medium text-emerald-600 dark:text-emerald-400"
                          : myShare.net_cents < 0
                            ? "text-destructive font-medium"
                            : "text-foreground font-medium"
                      }
                    >
                      {myShare.net_cents > 0
                        ? `${da.budget.netPositive} ${formatKr(myShare.net_cents)} kr`
                        : myShare.net_cents < 0
                          ? `${da.budget.netNegative} ${formatKr(-myShare.net_cents)} kr`
                          : da.budget.netZero}
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {budget && perFamily.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {isFinal ? da.budget.perFamily : da.budget.runningTitle}
            </CardTitle>
            {!isFinal && (
              <p className="text-muted-foreground text-sm">
                {da.budget.runningSubtitle}
              </p>
            )}
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground text-xs uppercase">
                <tr className="text-left">
                  <th className="pr-3 pb-2 font-medium">{da.budget.family}</th>
                  <th className="pr-3 pb-2 text-right font-medium">{da.budget.paid}</th>
                  <th className="pr-3 pb-2 text-right font-medium">{da.budget.share}</th>
                  <th className="pb-2 text-right font-medium">{da.budget.net}</th>
                </tr>
              </thead>
              <tbody>
                {perFamily.map((row) => {
                  const isMine = row.family_id === myFamilyId;
                  const netClass =
                    row.net_cents > 0
                      ? "text-emerald-600 dark:text-emerald-400 font-medium"
                      : row.net_cents < 0
                        ? "text-destructive font-medium"
                        : "text-muted-foreground";
                  return (
                    <tr key={row.family_id} className="border-t">
                      <td className="py-2 pr-3">
                        <span className={isMine ? "font-medium" : ""}>
                          {familyName(row.family_id)}
                        </span>
                        {isMine && (
                          <Badge variant="outline" className="ml-2">
                            Jer
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {formatKr(row.paid_cents)} kr
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {formatKr(row.share_cents)} kr
                      </td>
                      <td className={`py-2 text-right tabular-nums ${netClass}`}>
                        {row.net_cents > 0
                          ? `+${formatKr(row.net_cents)} kr`
                          : row.net_cents < 0
                            ? `−${formatKr(-row.net_cents)} kr`
                            : "0 kr"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {budget && budget.settlements.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{da.budget.settlements}</CardTitle>
            {!isFinal && (
              <p className="text-muted-foreground text-sm">
                {da.budget.settlementsHint}
              </p>
            )}
          </CardHeader>
          <CardContent className="grid gap-2">
            {budget.settlements.map((s, i) => (
              <div key={i} className="rounded-md border p-3 text-sm">
                {da.budget.settlementLine(
                  familyName(s.from_family_id),
                  familyName(s.to_family_id),
                  s.amount_cents / 100,
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Udgifter</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          {expenses && expenses.length === 0 && (
            <p className="text-muted-foreground text-sm">Ingen udgifter endnu.</p>
          )}
          {/* Edit dialog */}
          <Dialog
            open={editingId !== null}
            onOpenChange={(o) => !o && setEditingId(null)}
          >
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>{da.budget.editExpense}</DialogTitle>
              </DialogHeader>
              {editing && (
                <form
                  onSubmit={editForm.handleSubmit((v) =>
                    update.mutate({ id: editing.id, v }),
                  )}
                >
                  <FieldGroup>
                    <Field>
                      <FieldLabel htmlFor="edit-category">{da.budget.category}</FieldLabel>
                      <Select
                        value={editForm.watch("category_id")}
                        onValueChange={(v) => editForm.setValue("category_id", v)}
                      >
                        <SelectTrigger id="edit-category">
                          <SelectValue placeholder="Vælg kategori" />
                        </SelectTrigger>
                        <SelectContent>
                          {categories?.map((c) => (
                            <SelectItem key={c.id} value={String(c.id)}>
                              {c.name}
                              {c.is_utility ? " · forbrug" : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="edit-amount">{da.budget.amount}</FieldLabel>
                      <Input
                        id="edit-amount"
                        inputMode="decimal"
                        placeholder="0,00"
                        {...editForm.register("amount_kr")}
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="edit-desc">{da.budget.description}</FieldLabel>
                      <Input id="edit-desc" {...editForm.register("description")} />
                    </Field>
                    {flatChors.length > 0 && (
                      <Field>
                        <FieldLabel htmlFor="edit-chor">
                          {da.budget.chor}{" "}
                          <span className="text-muted-foreground text-xs">
                            {da.budget.chorOptional}
                          </span>
                        </FieldLabel>
                        <Select
                          value={editForm.watch("chor_id") ?? NO_CHOR}
                          onValueChange={(v) => editForm.setValue("chor_id", v)}
                        >
                          <SelectTrigger id="edit-chor" className="w-full">
                            <SelectValue placeholder={da.budget.chorNone} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={NO_CHOR}>{da.budget.chorNone}</SelectItem>
                            {flatChors.map((c) => (
                              <SelectItem key={c.id} value={String(c.id)}>
                                {c.date} · {MEAL_LABELS[c.meal] ?? c.meal} ·{" "}
                                {ACTION_LABELS[c.action] ?? c.action}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Field>
                    )}
                    {isAdmin && payers.length > 0 && (
                      <Field>
                        <FieldLabel htmlFor="edit-payer">{da.budget.paidBy}</FieldLabel>
                        <Select
                          value={editForm.watch("paid_by_user_id") ?? ""}
                          onValueChange={(v) =>
                            editForm.setValue("paid_by_user_id", v)
                          }
                        >
                          <SelectTrigger id="edit-payer" className="w-full">
                            <SelectValue placeholder={da.budget.changePayer} />
                          </SelectTrigger>
                          <SelectContent>
                            {payers.map((p) => (
                              <SelectItem key={p.id} value={String(p.id)}>
                                {p.name}
                                {p.email ? ` · ${p.email}` : ""}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Field>
                    )}
                    <DialogFooter>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setEditingId(null)}
                        disabled={update.isPending}
                      >
                        {da.common.cancel}
                      </Button>
                      <Button type="submit" disabled={update.isPending}>
                        {da.common.save}
                      </Button>
                    </DialogFooter>
                  </FieldGroup>
                </form>
              )}
            </DialogContent>
          </Dialog>

          {expenses?.map((e) => {
            const cat = categories?.find((c) => c.id === e.category_id);
            const chor = flatChors.find((c) => c.id === e.chor_id);
            const payerName =
              e.paid_by_user_name ??
              payers.find((p) => p.id === e.paid_by_user_id)?.name ??
              `#${e.paid_by_user_id}`;
            return (
              <div
                key={e.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="font-medium">
                    {formatKr(e.amount_cents)} {da.common.danishCurrency}
                  </p>
                  <p className="text-muted-foreground text-sm">
                    <Badge variant="outline" className="mr-1">
                      {cat?.name ?? `Kategori ${e.category_id}`}
                    </Badge>
                    {chor && (
                      <Badge variant="secondary" className="mr-1">
                        {MEAL_LABELS[chor.meal] ?? chor.meal} ·{" "}
                        {ACTION_LABELS[chor.action] ?? chor.action}
                      </Badge>
                    )}
                    {e.description}
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">
                    {da.budget.paidBy}: <span className="font-medium">{payerName}</span>
                  </p>
                </div>
                {canMutate(e) && (
                  <div className="flex items-center gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => beginEdit(e)}
                      aria-label={da.budget.editExpense}
                      title={da.budget.editExpense}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => remove.mutate(e.id)}
                      aria-label={da.budget.deleteExpense}
                      title={da.budget.deleteExpense}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
