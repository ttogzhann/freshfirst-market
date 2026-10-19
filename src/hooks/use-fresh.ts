import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getService, ServiceError, type ConfirmedSubstitution } from "@/services";

const svc = () => getService();

export function errorMessage(e: unknown): string {
  if (e instanceof ServiceError) return e.message;
  if (e instanceof Error) return `Something went wrong: ${e.message}`;
  return "Something went wrong. Please try again.";
}

export const useIngredients = () => useQuery({ queryKey: ["ingredients"], queryFn: () => svc().listIngredients(), staleTime: Infinity });
export const usePantry = () => useQuery({ queryKey: ["pantry"], queryFn: () => svc().listPantry() });
export const useRecipes = (query?: string, category?: string) =>
  useQuery({ queryKey: ["recipes", query, category], queryFn: () => svc().listRecipes({ query, category }) });
export const useRecipe = (id: string, servings?: number, subs: ConfirmedSubstitution[] = []) =>
  useQuery({ queryKey: ["recipe", id, servings, subs], queryFn: () => svc().getRecipe(id, servings, subs), placeholderData: (p) => p });
export const useBasket = () => useQuery({ queryKey: ["basket"], queryFn: () => svc().getBasket() });
export const useShopping = () => useQuery({ queryKey: ["shopping"], queryFn: () => svc().getShoppingList() });
export const useHistory = () => useQuery({ queryKey: ["history"], queryFn: () => svc().listHistory() });
export const useDashboard = () => useQuery({ queryKey: ["dashboard"], queryFn: () => svc().getDashboard() });

/** Mutation that toasts only after the service confirms, then refreshes every view. */
export function useAction<TArgs, TOut>(
  fn: (args: TArgs) => Promise<TOut>,
  success?: string | ((out: TOut) => string),
  opts: { silentErrors?: (e: unknown) => boolean } = {},
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (out) => {
      if (success) toast.success(typeof success === "function" ? success(out) : success);
      qc.invalidateQueries();
    },
    onError: (e) => {
      if (opts.silentErrors?.(e)) return;
      toast.error(errorMessage(e));
    },
  });
}

export { svc as service };
