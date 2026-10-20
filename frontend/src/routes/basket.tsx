import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { IngredientLines } from "@/components/fresh/IngredientLines";
import { CookDialog } from "@/components/fresh/CookDialog";
import { Empty, ErrorState, Loading, PageHeader } from "@/components/fresh/ui-bits";
import { service, useAction, useBasket, useRecipe } from "@/hooks/use-fresh";
import { formatQty } from "@/services/domain";
import type { BasketView } from "@/services";
import { quantityControlLabel } from "@/components/fresh/recipe-quantity";

export const Route = createFileRoute("/basket")({ component: BasketPage });

function BasketSelection({ item }: { item: BasketView["items"][number] }) {
  const [cooking, setCooking] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const detail = useRecipe(item.recipe_id, item.servings, item.substitutions);
  const update = useAction(
    (patch: Parameters<ReturnType<typeof service>["updateBasketItem"]>[1]) =>
      service().updateBasketItem(item.id, patch),
    "Basket updated",
  );
  const remove = useAction(() => service().removeBasketItem(item.id), "Recipe removed");
  return (
    <article className="space-y-4 rounded-xl border bg-card p-5">
      <Link to="/recipes/$id" params={{ id: item.recipe_id }} className="text-xl font-semibold">
        {item.recipe.title}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <label>
          {quantityControlLabel(item.recipe.base_servings)}{" "}
          <select
            aria-label={`${quantityControlLabel(item.recipe.base_servings)} for ${item.recipe.title}`}
            value={item.servings}
            disabled={update.isPending}
            onChange={(e) => update.mutate({ servings: Number(e.target.value) })}
          >
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <Button
          variant="outline"
          disabled={remove.isPending}
          onClick={() => remove.mutate(undefined)}
        >
          Remove
        </Button>
        <Button onClick={() => setCooking(true)}>I Cooked This</Button>
      </div>
      {detail.isLoading && <Loading />}
      {detail.error && <ErrorState error={detail.error} onRetry={detail.refetch} />}
      {detail.data && <IngredientLines lines={detail.data.lines} />}
      {detail.data?.suggestions
        .filter((s) => !rejected.includes(s.rule.id))
        .map((s) => (
          <div key={s.rule.id} className="space-y-2 text-sm">
            <p>
              Use {formatQty(s.required, s.unit)} {s.substitute_name} instead of {s.original_name}.{" "}
              {s.rule.context}: {s.rule.note}
            </p>
            <Button
              disabled={update.isPending}
              onClick={() =>
                update.mutate({
                  substitutions: [
                    ...item.substitutions,
                    {
                      rule_id: s.rule.id,
                      original_ingredient_id: s.rule.original_ingredient_id,
                      substitute_ingredient_id: s.rule.substitute_ingredient_id,
                    },
                  ],
                })
              }
            >
              Use substitute
            </Button>
            <Button variant="ghost" onClick={() => setRejected([...rejected, s.rule.id])}>
              No thanks
            </Button>
          </div>
        ))}
      {item.substitutions.length > 0 && (
        <Button
          variant="ghost"
          disabled={update.isPending}
          onClick={() => update.mutate({ substitutions: [] })}
        >
          Undo substitutions
        </Button>
      )}
      <CookDialog
        open={cooking}
        onOpenChange={setCooking}
        title={item.recipe.title}
        baseServings={item.recipe.base_servings}
        request={{
          recipe_id: item.recipe_id,
          servings: item.servings,
          substitutions: item.substitutions,
        }}
      />
    </article>
  );
}

export function BasketPage() {
  const basket = useBasket();
  if (basket.isLoading) return <Loading />;
  if (basket.error) return <ErrorState error={basket.error} onRetry={basket.refetch} />;
  return (
    <>
      <PageHeader
        title="Basket"
        subtitle="Plan recipe quantities and confirm substitutions before shopping or cooking."
        action={<Link to="/shopping">Open shopping list</Link>}
      />
      {!basket.data?.items.length ? (
        <Empty title="Your basket is empty">
          <Link to="/recipes">Browse recipes</Link>
        </Empty>
      ) : (
        <div className="space-y-6">
          {basket.data.items.map((item) => (
            <BasketSelection key={item.id} item={item} />
          ))}
          <h2 className="text-2xl font-semibold">Cumulative ingredients</h2>
          <IngredientLines lines={basket.data.totals} />
        </div>
      )}
    </>
  );
}
