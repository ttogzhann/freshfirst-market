import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Empty, ErrorState, Loading, PageHeader } from "@/components/fresh/ui-bits";
import { errorMessage, service, useAction, useIngredients, useShopping } from "@/hooks/use-fresh";
import { ServiceError, type ShoppingItem } from "@/services";

export const Route = createFileRoute("/shopping")({ component: ShoppingPage });

function ShoppingLine({ item }: { item: ShoppingItem }) {
  const [quantity, setQuantity] = useState(String(item.quantity));
  const [actual, setActual] = useState(String(item.quantity));
  const [expiry, setExpiry] = useState("");
  const update = useAction(
    (patch: { quantity?: number; purchased?: boolean }) =>
      service().updateShoppingItem(item.id, patch),
    "Shopping item updated",
  );
  const remove = useAction(() => service().removeShoppingItem(item.id), "Shopping item removed");
  const transfer = useAction(
    () => service().transferToPantry(item.id, { quantity: Number(actual), expiry_date: expiry }),
    "Purchase added to pantry",
  );
  return (
    <li className="space-y-3 rounded-xl border bg-card p-4">
      <label className="flex gap-2">
        <input
          type="checkbox"
          checked={item.purchased}
          disabled={update.isPending || item.transferred_to_pantry}
          onChange={(e) => update.mutate({ purchased: e.target.checked })}
        />
        {item.label} ({item.origin})
      </label>
      <form
        className="flex flex-wrap items-center gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate({ quantity: Number(quantity) });
        }}
      >
        <label>
          Quantity{" "}
          <input
            aria-label={`Quantity for ${item.label}`}
            className="w-24 rounded border p-2"
            type="number"
            min="0.01"
            step="0.01"
            required
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </label>
        <span>{item.unit}</span>
        <Button variant="outline" disabled={update.isPending || item.transferred_to_pantry}>
          Save quantity
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={remove.isPending}
          onClick={() => remove.mutate(undefined)}
        >
          Remove
        </Button>
      </form>
      {item.transferred_to_pantry ? (
        <p>Added to pantry</p>
      ) : (
        item.purchased &&
        (item.ingredient_id ? (
          <form
            className="flex flex-wrap items-center gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              transfer.mutate(undefined);
            }}
          >
            <label>
              Actual quantity ({item.unit}){" "}
              <input
                className="w-24 rounded border p-2"
                type="number"
                min="0.01"
                step="0.01"
                required
                value={actual}
                onChange={(e) => setActual(e.target.value)}
              />
            </label>
            <label>
              Expiry date{" "}
              <input
                type="date"
                required
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              />
            </label>
            <Button disabled={transfer.isPending}>Confirm transfer to pantry</Button>
            {transfer.error && <p role="alert">{errorMessage(transfer.error)}</p>}
          </form>
        ) : (
          <p>Only catalog ingredients can be transferred to pantry.</p>
        ))
      )}
    </li>
  );
}

export function ShoppingPage() {
  const shopping = useShopping();
  const ingredients = useIngredients();
  const [label, setLabel] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState("pcs");
  const [ingredient, setIngredient] = useState("");
  const [resetAll, setResetAll] = useState(false);
  const [confirmation, setConfirmation] = useState<{ resetAll: boolean } | null>(null);
  const generate = useAction(
    (opts: { resetAll: boolean; force?: boolean }) => service().generateShoppingList(opts),
    "Shopping list generated",
    { silentErrors: (e) => e instanceof ServiceError && e.code === "EDITS_WOULD_BE_LOST" },
  );
  const add = useAction(
    () =>
      service().addShoppingItem({
        label,
        quantity: Number(quantity),
        unit,
        ingredient_id: ingredient || null,
      }),
    "Shopping item added",
  );
  function regenerate(opts: { resetAll: boolean; force?: boolean }) {
    generate.mutate(opts, {
      onError: (e) => {
        if (e instanceof ServiceError && e.code === "EDITS_WOULD_BE_LOST")
          setConfirmation({ resetAll: opts.resetAll });
      },
      onSuccess: () => setConfirmation(null),
    });
  }
  if (shopping.isLoading || ingredients.isLoading) return <Loading />;
  if (shopping.error || ingredients.error)
    return (
      <ErrorState
        error={shopping.error || ingredients.error}
        onRetry={() => {
          shopping.refetch();
          ingredients.refetch();
        }}
      />
    );
  return (
    <>
      <PageHeader
        title="Shopping List"
        subtitle="Combined basket needs minus usable pantry stock, counted once."
        action={<Link to="/basket">Review basket</Link>}
      />
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Button disabled={generate.isPending} onClick={() => regenerate({ resetAll })}>
          Generate from basket
        </Button>
        <label>
          <input
            type="checkbox"
            checked={resetAll}
            onChange={(e) => setResetAll(e.target.checked)}
          />{" "}
          Reset manual items too
        </label>
      </div>
      {confirmation && (
        <div
          role="alertdialog"
          aria-label="Confirm regeneration"
          className="mb-6 rounded border p-4"
        >
          <p>
            Regenerating will overwrite edited or purchased generated lines
            {confirmation.resetAll ? " and remove manual items" : "; manual items will be kept"}.
            Continue?
          </p>
          <Button
            disabled={generate.isPending}
            onClick={() => regenerate({ ...confirmation, force: true })}
          >
            Confirm regeneration
          </Button>
          <Button variant="ghost" onClick={() => setConfirmation(null)}>
            Cancel
          </Button>
        </div>
      )}
      <form
        className="mb-6 flex flex-wrap items-end gap-3 rounded-xl border p-4"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate(undefined, { onSuccess: () => setLabel("") });
        }}
      >
        <label>
          Catalog ingredient{" "}
          <select
            value={ingredient}
            onChange={(e) => {
              const i = ingredients.data?.find((i) => i.id === e.target.value);
              setIngredient(e.target.value);
              if (i) {
                setLabel(i.name);
                setUnit(i.canonical_unit);
              }
            }}
          >
            <option value="">Other manual item</option>
            {ingredients.data?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Name{" "}
          <input
            className="rounded border p-2"
            required
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>
        <label>
          Quantity{" "}
          <input
            className="w-24 rounded border p-2"
            required
            type="number"
            min="0.01"
            step="0.01"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </label>
        <label>
          Unit{" "}
          <input
            className="w-20 rounded border p-2"
            required
            disabled={!!ingredient}
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
          />
        </label>
        <Button disabled={add.isPending}>Add manual item</Button>
        {add.error && <p role="alert">{errorMessage(add.error)}</p>}
      </form>
      {!shopping.data?.length ? (
        <Empty title="Your shopping list is empty">
          Add a manual item or generate from your basket.
        </Empty>
      ) : (
        <ul className="space-y-3">
          {shopping.data.map((item) => (
            <ShoppingLine key={`${item.id}:${item.quantity}`} item={item} />
          ))}
        </ul>
      )}
    </>
  );
}
