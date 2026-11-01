import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/auth/useAuth";
import { getService, ServiceError, type ConfirmedSubstitution } from "@/services";

const svc = () => getService();

function usePrivateQuery<TData>(queryKey: QueryKey, queryFn: () => Promise<TData>) {
  const { status } = useAuth();
  return useQuery({
    queryKey,
    queryFn,
    enabled: status === "authenticated",
  });
}

export function errorMessage(e: unknown): string {
  if (e instanceof ServiceError) return e.message;
  if (e instanceof Error) return `Something went wrong: ${e.message}`;
  return "Something went wrong. Please try again.";
}

export const useIngredients = () =>
  useQuery({
    queryKey: ["ingredients"],
    queryFn: () => svc().listIngredients(),
    staleTime: Infinity,
  });
export const usePantry = () => usePrivateQuery(["pantry"], () => svc().listPantry());
export const useRecipes = (query?: string, category?: string, sort: "match" | "title" = "match") =>
  usePrivateQuery(["recipes", query, category, sort], () =>
    svc().listRecipes({ ...(query ? { query } : {}), ...(category ? { category } : {}), sort }),
  );
export const useRecipe = (id: string, servings?: number, subs: ConfirmedSubstitution[] = []) =>
  usePrivateQuery(["recipe", id, servings, subs], () => svc().getRecipe(id, servings, subs));
export const useBasket = () => usePrivateQuery(["basket"], () => svc().getBasket());
export const useShopping = () => usePrivateQuery(["shopping"], () => svc().getShoppingList());
export const useHistory = () => usePrivateQuery(["history"], () => svc().listHistory());
export const useDashboard = () => usePrivateQuery(["dashboard"], () => svc().getDashboard());

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
    },
    // A failed multi-request action or lost response can still have changed server state.
    onSettled: () => qc.invalidateQueries(),
    onError: (e) => {
      if (opts.silentErrors?.(e)) return;
      toast.error(errorMessage(e));
    },
  });
}

export { svc as service };
