import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, Clock, Package } from "lucide-react";
import { useDashboard } from "@/hooks/use-fresh";
import { recipeQuantity } from "@/components/fresh/recipe-quantity";
import {
  Empty,
  ErrorState,
  Loading,
  MatchPill,
  PageHeader,
  RecipeImage,
} from "@/components/fresh/ui-bits";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — FreshFirst" },
      { name: "description", content: "See what's expiring and which recipes to cook first." },
      { property: "og:title", content: "Dashboard — FreshFirst" },
      {
        property: "og:description",
        content: "See what's expiring and which recipes to cook first.",
      },
    ],
  }),
  component: Dashboard,
});

export function Dashboard() {
  const { data, isLoading, error, refetch } = useDashboard();
  return (
    <>
      <PageHeader title="Good to see you" subtitle="Here's what needs using up soon." />
      {isLoading && <Loading />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && (
        <div className="space-y-10">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat icon={Package} label="Pantry items" value={data.total_items} to="/pantry" />
            <Stat
              icon={Clock}
              label="Expiring in 3 days"
              value={data.expiring_soon}
              tone="warning"
              to="/pantry"
            />
            <Stat
              icon={AlertTriangle}
              label="Expired"
              value={data.expired}
              tone="destructive"
              to="/pantry"
            />
          </div>

          <section>
            <h2 className="mb-4 text-2xl font-semibold">Cook these first</h2>
            {data.recommendations.length === 0 ? (
              <Empty title="No recipes yet" />
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {data.recommendations.map((r) => (
                  <Link
                    key={r.id}
                    to="/recipes/$id"
                    params={{ id: r.id }}
                    className="group overflow-hidden rounded-xl border bg-card shadow-card transition hover:-translate-y-0.5"
                  >
                    <RecipeImage src={r.image_url} alt={r.title} className="aspect-[4/3]" />
                    <div className="space-y-2 p-4">
                      <MatchPill score={r.match.score} />
                      <p className="font-display text-lg leading-tight">{r.title}</p>
                      {r.match.expiring_used.length > 0 && (
                        <p className="text-xs text-warning-foreground">
                          Uses soon-expiring {r.match.expiring_used.join(", ")}
                        </p>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-4 text-2xl font-semibold">Recently cooked</h2>
            {data.recent_history.length === 0 ? (
              <Empty title="Nothing cooked yet">
                Open a recipe and tap “I cooked this” to log it.
              </Empty>
            ) : (
              <ul className="divide-y rounded-xl border bg-card">
                {data.recent_history.map((h) => (
                  <li key={h.id} className="flex justify-between px-4 py-3 text-sm">
                    <span className="font-medium">{h.recipe_title}</span>
                    <span className="text-muted-foreground">
                      {recipeQuantity(h.servings)} · {new Date(h.cooked_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone,
  to,
}: {
  icon: typeof Package;
  label: string;
  value: number;
  tone?: "warning" | "destructive";
  to: "/pantry";
}) {
  const color =
    tone === "warning"
      ? "text-warning-foreground bg-warning/30"
      : tone === "destructive"
        ? "text-destructive bg-destructive/10"
        : "text-primary bg-secondary";
  return (
    <Link to={to} className="flex items-center gap-4 rounded-xl border bg-card p-5 shadow-card">
      <span className={`flex h-11 w-11 items-center justify-center rounded-full ${color}`}>
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <p className="font-display text-3xl font-semibold">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </Link>
  );
}
