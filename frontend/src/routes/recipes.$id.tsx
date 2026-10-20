import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChefHat, Minus, Plus, ShoppingBasket, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { service, useAction, useBasket, useRecipe } from "@/hooks/use-fresh";
import { formatQty, MAX_SERVINGS, MIN_SERVINGS } from "@/services/domain";
import type { ConfirmedSubstitution } from "@/services";
import { ErrorState, Loading, MatchPill, RecipeImage } from "@/components/fresh/ui-bits";
import { IngredientLines } from "@/components/fresh/IngredientLines";
import { CookDialog } from "@/components/fresh/CookDialog";
import { quantityControlLabel, recipeQuantity } from "@/components/fresh/recipe-quantity";
import { EXPIRY_THRESHOLD_DAYS } from "@/config";

export const Route = createFileRoute("/recipes/$id")({
  head: () => ({
    meta: [
      { title: "Recipe — FreshFirst" },
      { name: "description", content: "Recipe details, pantry availability and substitutions." },
      { property: "og:title", content: "Recipe — FreshFirst" },
      {
        property: "og:description",
        content: "Recipe details, pantry availability and substitutions.",
      },
    ],
  }),
  component: RecipePage,
});

export function RecipePage() {
  const { id } = Route.useParams();
  const [choices, setChoices] = useState<{
    recipeId: string;
    servings: number | undefined;
    substitutions: ConfirmedSubstitution[];
  } | null>(null);
  const [rejections, setRejections] = useState<{ recipeId: string; ruleIds: string[] } | null>(
    null,
  );
  const [cooking, setCooking] = useState(false);
  const queryClient = useQueryClient();
  const basket = useBasket();
  const inBasket = basket.data?.items.find((b) => b.recipe_id === id);
  const activeChoices = choices?.recipeId === id ? choices : null;
  const servings = activeChoices ? activeChoices.servings : inBasket?.servings;
  const subs = activeChoices ? activeChoices.substitutions : (inBasket?.substitutions ?? []);
  const rejected = rejections?.recipeId === id ? rejections.ruleIds : [];
  const { data, isLoading, error, refetch } = useRecipe(id, servings, subs);

  useEffect(() => {
    setChoices(null);
    setRejections(null);
  }, [id]);

  const s = data?.servings ?? 2;
  const add = useAction(
    async () => {
      let item = await service().addToBasket(id, s);
      const savedSubs = inBasket?.substitutions ?? [];
      if (!sameSubstitutions(subs, savedSubs)) {
        try {
          item = await service().updateBasketItem(item.id, { substitutions: subs });
        } catch (error) {
          try {
            const persisted = await service().getBasket();
            queryClient.setQueryData(["basket"], persisted);
            const actual = persisted.items.find((selection) => selection.recipe_id === id);
            setChoices(
              actual
                ? {
                    recipeId: id,
                    servings: actual.servings,
                    substitutions: actual.substitutions,
                  }
                : null,
            );
          } catch {
            setChoices(null);
          }
          throw error;
        }
      }
      setChoices({
        recipeId: id,
        servings: item.servings,
        substitutions: item.substitutions,
      });
      return item;
    },
    inBasket ? "Basket updated" : "Added to basket",
  );

  if (basket.isLoading || isLoading) return <Loading />;
  if (basket.error) return <ErrorState error={basket.error} onRetry={basket.refetch} />;
  if (error)
    return (
      <>
        <ErrorState error={error} onRetry={refetch} />
        {(subs.length > 0 || servings !== undefined) && (
          <Button
            variant="outline"
            onClick={() => {
              setChoices({ recipeId: id, servings: undefined, substitutions: [] });
            }}
          >
            Reset recipe choices
          </Button>
        )}
      </>
    );
  if (!data) return null;

  const suggestions = data.suggestions.filter((x) => !rejected.includes(x.rule.id));

  return (
    <>
      <Link
        to="/recipes"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> All recipes
      </Link>
      <div className="grid gap-8 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <RecipeImage src={data.image_url} alt={data.title} className="aspect-[4/3] rounded-2xl" />
        </div>
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            <MatchPill score={data.match.score} />
            <span className="text-sm text-muted-foreground">
              {data.category} · {recipeQuantity(data.base_servings, data.base_servings)}
            </span>
          </div>
          <h1 className="text-4xl font-semibold">{data.title}</h1>
          <p className="text-sm text-muted-foreground">
            {data.base_servings === 1
              ? "One batch uses the complete source ingredient quantities."
              : `Source ingredient quantities correspond to recipe quantity ${data.base_servings}.`}
          </p>
          {data.match.expiring_used.length > 0 && (
            <p className="rounded-lg bg-warning/25 px-3 py-2 text-sm text-warning-foreground">
              Uses {data.match.expiring_used.join(", ")}, which expire within{" "}
              {EXPIRY_THRESHOLD_DAYS} days.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center rounded-lg border bg-card">
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Decrease ${quantityControlLabel(data.base_servings).toLowerCase()}`}
                disabled={s <= MIN_SERVINGS}
                onClick={() => setChoices({ recipeId: id, servings: s - 1, substitutions: subs })}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <span className="min-w-24 px-2 text-center text-sm font-medium">
                {recipeQuantity(s, data.base_servings)}
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Increase ${quantityControlLabel(data.base_servings).toLowerCase()}`}
                disabled={s >= MAX_SERVINGS}
                onClick={() => setChoices({ recipeId: id, servings: s + 1, substitutions: subs })}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <Button
              variant="outline"
              disabled={add.isPending}
              onClick={() => add.mutate(undefined)}
            >
              <ShoppingBasket className="h-4 w-4" />{" "}
              {inBasket ? `Update basket (${inBasket.servings} → ${s})` : "Add to basket"}
            </Button>
            <Button onClick={() => setCooking(true)}>
              <ChefHat className="h-4 w-4" /> I cooked this
            </Button>
          </div>

          <IngredientLines lines={data.lines} />

          {suggestions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">Suggested substitutions</h3>
              {suggestions.map((sg) => (
                <div
                  key={sg.rule.id}
                  className="rounded-xl border border-accent bg-accent/30 p-3 text-sm"
                >
                  <p>
                    Use{" "}
                    <b>
                      {formatQty(sg.required, sg.unit)} {sg.substitute_name}
                    </b>{" "}
                    instead of {sg.original_name}
                    <span className="text-muted-foreground"> · {sg.rule.context}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">{sg.rule.note}</p>
                  <div className="mt-2 flex gap-2">
                    <Button
                      size="sm"
                      onClick={() =>
                        setChoices({
                          recipeId: id,
                          servings: s,
                          substitutions: [
                            ...subs,
                            {
                              rule_id: sg.rule.id,
                              original_ingredient_id: sg.rule.original_ingredient_id,
                              substitute_ingredient_id: sg.rule.substitute_ingredient_id,
                            },
                          ],
                        })
                      }
                    >
                      Use substitute
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setRejections({ recipeId: id, ruleIds: [...rejected, sg.rule.id] })
                      }
                    >
                      No thanks
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {subs.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setChoices({ recipeId: id, servings: s, substitutions: [] })}
            >
              <Undo2 className="h-4 w-4" /> Undo substitutions
            </Button>
          )}
        </div>
      </div>
      <section className="mt-10 max-w-3xl">
        <h2 className="mb-3 text-2xl font-semibold">Method</h2>
        <p className="leading-relaxed text-muted-foreground">{data.instructions}</p>
      </section>
      <CookDialog
        open={cooking}
        onOpenChange={setCooking}
        title={data.title}
        baseServings={data.base_servings}
        request={{ recipe_id: id, servings: s, substitutions: subs }}
      />
    </>
  );
}

function sameSubstitutions(left: ConfirmedSubstitution[], right: ConfirmedSubstitution[]): boolean {
  return (
    left.length === right.length &&
    left.every((substitution) =>
      right.some(
        (saved) =>
          saved.rule_id === substitution.rule_id &&
          saved.original_ingredient_id === substitution.original_ingredient_id &&
          saved.substitute_ingredient_id === substitution.substitute_ingredient_id,
      ),
    )
  );
}
