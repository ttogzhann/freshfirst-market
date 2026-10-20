import { useEffect, useState } from "react";
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
import type { CookPreview, CookRequest } from "@/services";
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

  useEffect(() => {
    if (!open) return;
    let active = true;
    setPreview(null);
    setError(null);
    service()
      .previewCook(request)
      .then((value) => {
        if (active) setPreview(value);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, JSON.stringify(request)]);

  async function confirm() {
    setBusy(true);
    try {
      await service().confirmCook(request);
      toast.success(`Enjoy your ${title}! Pantry updated.`);
      qc.invalidateQueries();
      onOpenChange(false);
    } catch (e) {
      toast.error(errorMessage(e));
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
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!preview && !error && <Loading label="Checking pantry…" />}
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
            Cancel
          </Button>
          <Button disabled={!preview?.can_cook || busy} onClick={confirm}>
            {busy ? "Saving…" : "Confirm & deduct"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
