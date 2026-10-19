import { CheckCircle2, CircleAlert } from "lucide-react";
import { formatQty } from "@/services/domain";
import type { DemandLine } from "@/services";

export function IngredientLines({ lines }: { lines: DemandLine[] }) {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {lines.map((l) => (
        <li key={l.ingredient_id + (l.substituted_from ?? "")} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
          <span className="flex items-center gap-2">
            {l.sufficient ? <CheckCircle2 className="h-4 w-4 text-success" /> : <CircleAlert className="h-4 w-4 text-destructive" />}
            <span className="font-medium">{l.name}</span>
            {l.substituted_from && <span className="rounded bg-accent px-1.5 text-xs text-accent-foreground">substitute</span>}
          </span>
          <span className="tabular-nums">
            {formatQty(l.required, l.unit)}
            <span className="ml-2 text-xs text-muted-foreground">have {formatQty(l.available, l.unit)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
