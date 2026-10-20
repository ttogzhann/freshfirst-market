import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { errorMessage, service, useAction, useIngredients, usePantry } from "@/hooks/use-fresh";
import {
  addDays,
  compatibleUnits,
  daysUntil,
  expiryStatus,
  formatQty,
  isValidDate,
  todayISO,
} from "@/services/domain";
import { ServiceError, type InputUnit, type PantryItem } from "@/services";
import { Empty, ErrorState, ExpiryBadge, Loading, PageHeader } from "@/components/fresh/ui-bits";

export const Route = createFileRoute("/pantry")({
  head: () => ({
    meta: [
      { title: "Pantry — FreshFirst" },
      { name: "description", content: "Track what's in your pantry and when it expires." },
      { property: "og:title", content: "Pantry — FreshFirst" },
      { property: "og:description", content: "Track what's in your pantry and when it expires." },
    ],
  }),
  component: Pantry,
});

export function Pantry() {
  const pantry = usePantry();
  const ingredients = useIngredients();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [status, setStatus] = useState("all");
  const [editing, setEditing] = useState<PantryItem | "new" | null>(null);
  const remove = useAction((id: string) => service().deletePantryItem(id), "Item removed");
  const today = todayISO();
  const ingMap = useMemo(
    () => new Map((ingredients.data ?? []).map((i) => [i.id, i])),
    [ingredients.data],
  );
  const categories = [...new Set((ingredients.data ?? []).map((i) => i.category))];

  const rows = (pantry.data ?? [])
    .map((p) => ({
      p,
      ing: ingMap.get(p.ingredient_id)!,
      st: expiryStatus(p.expiry_date, today),
      days: daysUntil(p.expiry_date, today),
    }))
    .filter((r) => r.ing)
    .filter((r) => !q || r.ing.name.toLowerCase().includes(q.toLowerCase()))
    .filter((r) => cat === "all" || r.ing.category === cat)
    .filter((r) => status === "all" || r.st === status)
    .sort((a, b) => a.days - b.days);

  return (
    <>
      <PageHeader
        title="Pantry"
        subtitle="Expired items stay visible but don't count as available."
        action={
          <Button
            disabled={ingredients.isLoading || !!ingredients.error}
            onClick={() => setEditing("new")}
          >
            <Plus className="h-4 w-4" /> Add item
          </Button>
        }
      />
      <div className="mb-6 flex flex-wrap gap-3">
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search pantry…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-44" aria-label="Expiry status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any status</SelectItem>
            <SelectItem value="fresh">Fresh</SelectItem>
            <SelectItem value="expiring">Expiring soon</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {(pantry.isLoading || ingredients.isLoading) && <Loading />}
      {pantry.error && <ErrorState error={pantry.error} onRetry={pantry.refetch} />}
      {ingredients.error && <ErrorState error={ingredients.error} onRetry={ingredients.refetch} />}
      {pantry.data && ingredients.data && rows.length === 0 && (
        <Empty title={pantry.data.length ? "No items match your filters" : "Your pantry is empty"}>
          Add what you have to get recipe suggestions.
        </Empty>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map(({ p, ing, st, days }) => (
          <div
            key={p.id}
            className={`rounded-xl border bg-card p-4 shadow-card ${st === "expired" ? "opacity-70" : ""} ${st === "expiring" ? "border-warning" : ""}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-display text-lg leading-tight">{ing.name}</p>
                <p className="text-xs text-muted-foreground">{ing.category}</p>
              </div>
              <ExpiryBadge status={st} days={days} />
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div>
                <p className="text-2xl font-semibold tabular-nums">
                  {formatQty(p.quantity, ing.canonical_unit)}
                </p>
                <p className="text-xs text-muted-foreground">Best before {p.expiry_date}</p>
              </div>
              <div className="flex gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Edit ${ing.name}`}
                  onClick={() => setEditing(p)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove ${ing.name}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(p.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {editing && (
        <PantryForm item={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </>
  );
}

function PantryForm({ item, onClose }: { item: PantryItem | null; onClose: () => void }) {
  const { data: ingredients = [] } = useIngredients();
  const [ingredientId, setIngredientId] = useState(item?.ingredient_id ?? "");
  const ing = ingredients.find((i) => i.id === ingredientId);
  const [unit, setUnit] = useState<InputUnit>((ing?.canonical_unit as InputUnit) ?? "pcs");
  const [qty, setQty] = useState(item ? String(item.quantity) : "");
  const [expiry, setExpiry] = useState(item?.expiry_date ?? addDays(todayISO(), 7));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = useAction(
    () => {
      const input = {
        ingredient_id: ingredientId,
        quantity: Number(qty),
        unit,
        expiry_date: expiry,
      };
      return item ? service().updatePantryItem(item.id, input) : service().createPantryItem(input);
    },
    item ? "Pantry item updated" : "Added to pantry",
  );
  const mutationError = save.error;
  const mutationMessage = mutationError ? errorMessage(mutationError) : "";
  const expiryConflict =
    mutationError instanceof ServiceError && mutationError.code === "EXPIRY_CONFLICT";
  const actionableMutationMessage =
    expiryConflict && !/edit|same expiry|match/i.test(mutationMessage)
      ? `${mutationMessage} Use the same expiry date as the existing pantry entry or edit that entry first.`
      : mutationMessage;
  const serviceQuantityError =
    mutationError instanceof ServiceError &&
    mutationError.code === "VALIDATION_ERROR" &&
    /quantity/i.test(mutationMessage)
      ? mutationMessage
      : "";
  const serviceExpiryError =
    expiryConflict ||
    (mutationError instanceof ServiceError &&
      mutationError.code === "VALIDATION_ERROR" &&
      /date|expiry/i.test(mutationMessage))
      ? actionableMutationMessage
      : "";
  const generalMutationError =
    mutationError && !serviceQuantityError && !serviceExpiryError ? actionableMutationMessage : "";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!ingredientId) errs["ingredient"] = "Choose an ingredient";
    if (!Number.isFinite(Number(qty)) || !(Number(qty) > 0))
      errs["qty"] = "Enter a finite quantity above zero";
    if (!isValidDate(expiry)) errs["expiry"] = "Enter a valid calendar date";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    save.mutate(undefined, { onSuccess: onClose });
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {item ? "Edit item" : "Add to pantry"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label>Ingredient</Label>
            <Select
              value={ingredientId}
              onValueChange={(v) => {
                setIngredientId(v);
                const next = ingredients.find((i) => i.id === v);
                if (next) setUnit(next.canonical_unit);
              }}
            >
              <SelectTrigger aria-label="Ingredient">
                <SelectValue placeholder="Choose from catalog" />
              </SelectTrigger>
              <SelectContent>
                {ingredients.map((i) => (
                  <SelectItem key={i.id} value={i.id}>
                    {i.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors["ingredient"] && (
              <p className="text-xs text-destructive">{errors["ingredient"]}</p>
            )}
          </div>
          <div className="grid grid-cols-[1fr_8rem] gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="qty">Quantity</Label>
              <Input
                id="qty"
                type="number"
                min="0"
                step="any"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
              />
              {(errors["qty"] || serviceQuantityError) && (
                <p role="alert" className="text-xs text-destructive">
                  {errors["qty"] || serviceQuantityError}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Unit</Label>
              <Select value={unit} onValueChange={(v) => setUnit(v as InputUnit)} disabled={!ing}>
                <SelectTrigger aria-label="Unit">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(ing ? compatibleUnits(ing.canonical_unit) : (["pcs"] as InputUnit[])).map(
                    (u) => (
                      <SelectItem key={u} value={u}>
                        {u}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="expiry">Expiry date</Label>
            <Input
              id="expiry"
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
            {(errors["expiry"] || serviceExpiryError) && (
              <p role="alert" className="text-xs text-destructive">
                {errors["expiry"] || serviceExpiryError}
              </p>
            )}
          </div>
          {generalMutationError && (
            <p role="alert" className="text-xs text-destructive">
              {generalMutationError}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
