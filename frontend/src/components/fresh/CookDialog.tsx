import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { errorMessage, service } from "@/hooks/use-fresh";
import { formatQty } from "@/services/domain";
import { ServiceError, type CookPreview, type CookRequest, type CookingRecord } from "@/services";
import { Loading } from "./ui-bits";
import { recipeQuantity } from "./recipe-quantity";

export function CookDialog({
  request,
  title,
  baseServings,
  open,
  onOpenChange,
}: {
  request: CookRequest;
  title: string;
  baseServings?: number;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<CookPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [unknownOutcome, setUnknownOutcome] = useState(false);
  const previewRequestId = useRef(0);

  async function loadPreview() {
    const requestId = ++previewRequestId.current;
    setPreview(null);
    setError(null);
    setLoadingPreview(true);
    try {
      const value = await service().previewCook(request);
      if (requestId === previewRequestId.current) setPreview(value);
    } catch (e) {
      if (requestId === previewRequestId.current) setError(errorMessage(e));
    } finally {
      if (requestId === previewRequestId.current) setLoadingPreview(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    setUnknownOutcome(false);
    void loadPreview();
    return () => {
      previewRequestId.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, JSON.stringify(request)]);

  function validDateTime(value: unknown): value is string {
    if (typeof value !== "string") return false;
    const match =
      /^(\d{4})-(\d{2})-(\d{2})[Tt]([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d+)?([Zz]|[+-](\d{2}):([0-5]\d))$/.exec(
        value,
      );
    if (!match) return false;

    const [, year, month, day, , , , zone, offsetHours] = match;
    const yearNumber = Number(year);
    const monthNumber = Number(month);
    const dayNumber = Number(day);
    const daysInMonth = [
      31,
      (yearNumber % 4 === 0 && yearNumber % 100 !== 0) || yearNumber % 400 === 0 ? 29 : 28,
      31,
      30,
      31,
      30,
      31,
      31,
      30,
      31,
      30,
      31,
    ][monthNumber - 1];
    return (
      dayNumber >= 1 &&
      dayNumber <= daysInMonth! &&
      (offsetHours === undefined || Number(offsetHours) <= 23)
    );
  }

  function validRecord(record: unknown): record is CookingRecord {
    if (record === null || typeof record !== "object") return false;
    const value = record as Partial<CookingRecord>;
    return (
      typeof value.id === "string" &&
      value.recipe_id === request.recipe_id &&
      typeof value.recipe_title === "string" &&
      typeof value.servings === "number" &&
      Number.isInteger(value.servings) &&
      value.servings >= 1 &&
      value.servings <= 8 &&
      value.servings === request.servings &&
      validDateTime(value.cooked_at) &&
      Array.isArray(value.consumed) &&
      Array.from(value.consumed).every(
        (line) =>
          line !== null &&
          typeof line === "object" &&
          typeof line.ingredient_id === "string" &&
          typeof line.quantity === "number" &&
          Number.isFinite(line.quantity) &&
          line.quantity >= 0,
      )
    );
  }

  async function confirm() {
    setBusy(true);
    try {
      const record = await service().confirmCook(request);
      if (!validRecord(record))
        throw new Error("FreshFirst returned an unreadable cooking result.");
      toast.success(`Enjoy your ${title}! Pantry updated.`);
      await qc.invalidateQueries({ refetchType: "all" });
      onOpenChange(false);
    } catch (e) {
      if (e instanceof ServiceError && e.status === 409 && e.code === "INSUFFICIENT_STOCK") {
        setPreview(null);
        setError(null);
        setLoadingPreview(true);
        await qc.invalidateQueries({ refetchType: "all" });
        await loadPreview();
      } else if (e instanceof ServiceError && (e.status === 404 || e.status === 422)) {
        setPreview(null);
        setUnknownOutcome(false);
        setError(errorMessage(e));
      } else {
        setPreview(null);
        setUnknownOutcome(true);
        setError(
          "Cooking outcome unknown. Inspect Pantry and recent cooking history before deciding what to do. Close this dialog to refresh the preview; cooking will not be retried automatically.",
        );
        void qc.invalidateQueries({ refetchType: "all" });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">I cooked {title}</DialogTitle>
          <DialogDescription>
            These amounts will be taken from your pantry (
            {recipeQuantity(request.servings, baseServings)}).
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="space-y-2">
            <p className="text-sm text-destructive">{error}</p>
            {!unknownOutcome && !loadingPreview && (
              <Button variant="outline" onClick={() => void loadPreview()}>
                Retry preview
              </Button>
            )}
          </div>
        )}
        {!preview && loadingPreview && <Loading label="Checking pantry…" />}
        {preview && (
          <ul className="divide-y rounded-lg border">
            {preview.lines.map((l) => (
              <li
                key={l.ingredient_id + (l.substituted_from ?? "")}
                className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2">
                  {l.sufficient ? (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  {l.name}
                  {l.substituted_from && (
                    <span className="text-xs text-muted-foreground">(substitute)</span>
                  )}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  −{formatQty(l.required, l.unit)}{" "}
                  <span className="text-xs">/ have {formatQty(l.available, l.unit)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {preview && !preview.can_cook && (
          <p className="text-sm text-destructive">
            Some ingredients are short. Restock or confirm a substitute first — nothing will be
            deducted.
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {unknownOutcome ? "Close" : "Cancel"}
          </Button>
          <Button disabled={!preview?.can_cook || busy || unknownOutcome} onClick={confirm}>
            {busy ? "Saving…" : "Confirm & deduct"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
