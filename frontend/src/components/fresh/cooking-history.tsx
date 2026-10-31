import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useHistory } from "@/hooks/use-fresh";
import type { CookingRecord } from "@/services";
import { recipeQuantity } from "./recipe-quantity";
import { Empty, ErrorState, Loading } from "./ui-bits";

function HistoryRows({ records }: { records: CookingRecord[] }) {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {records.map((record) => (
        <li
          key={record.id}
          className="flex flex-col gap-1 break-words px-4 py-3 text-sm sm:flex-row sm:justify-between sm:gap-4"
        >
          <span className="min-w-0 font-medium">{record.recipe_title}</span>
          <span className="shrink-0 text-muted-foreground">
            {recipeQuantity(record.servings)} ·{" "}
            <time dateTime={record.cooked_at}>{new Date(record.cooked_at).toLocaleString()}</time>
          </span>
        </li>
      ))}
    </ul>
  );
}

function CompleteHistory() {
  const { data, isLoading, error, refetch } = useHistory();
  if (isLoading) return <Loading label="Loading cooking history…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data?.length) return <Empty title="No cooking history yet" />;
  const records = [...data].sort((a, b) => Date.parse(b.cooked_at) - Date.parse(a.cooked_at));
  return <HistoryRows records={records} />;
}

export function CookingHistory({ recent }: { recent: CookingRecord[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section aria-labelledby="cooking-history-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id="cooking-history-heading" className="text-2xl font-semibold">
          {expanded ? "Cooking history" : "Recently cooked"}
        </h2>
        <Button
          variant="outline"
          aria-expanded={expanded}
          aria-controls="cooking-history-records"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Show recent only" : "View all cooking history"}
        </Button>
      </div>
      <div id="cooking-history-records">
        {expanded ? (
          <CompleteHistory />
        ) : recent.length ? (
          <HistoryRows records={recent} />
        ) : (
          <Empty title="Nothing cooked yet">Open a recipe and tap “I cooked this” to log it.</Empty>
        )}
      </div>
    </section>
  );
}
