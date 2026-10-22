import { useRef, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Download, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { service, useAction, useRecipes } from "@/hooks/use-fresh";
import type { ImportReport } from "@/services";
import {
  Empty,
  ErrorState,
  Loading,
  MatchPill,
  PageHeader,
  RecipeImage,
} from "@/components/fresh/ui-bits";

export const Route = createFileRoute("/recipes/")({
  head: () => ({
    meta: [
      { title: "Recipes — FreshFirst" },
      {
        name: "description",
        content: "Recipes ranked by what's in your pantry and what expires first.",
      },
      { property: "og:title", content: "Recipes — FreshFirst" },
      {
        property: "og:description",
        content: "Recipes ranked by what's in your pantry and what expires first.",
      },
    ],
  }),
  component: Recipes,
});

export function Recipes() {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [sort, setSort] = useState<"match" | "title">("match");
  const all = useRecipes();
  const list = useRecipes(q || undefined, cat === "all" ? undefined : cat, sort);
  const categories = [...new Set((all.data ?? []).map((r) => r.category))].sort();
  const [report, setReport] = useState<ImportReport | null>(null);
  const importButtonRef = useRef<HTMLButtonElement>(null);
  const imp = useAction(
    () => service().importRecipes(),
    (r) => `Import done: ${r.imported} new, ${r.updated} updated`,
  );

  return (
    <>
      <PageHeader
        title="Recipes"
        subtitle="Ranked by how much you already have, with soon-expiring items as a tie-breaker."
        action={
          <Button
            ref={importButtonRef}
            variant="outline"
            disabled={imp.isPending}
            onClick={() => imp.mutate(undefined, { onSuccess: setReport })}
          >
            <Download className="h-4 w-4" /> {imp.isPending ? "Importing…" : "Re-import recipes"}
          </Button>
        }
      />
      <div className="mb-6 flex flex-wrap gap-3">
        <label>
          Sort recipes{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value as "match" | "title")}>
            <option value="match">Best match</option>
            <option value="title">Title</option>
          </select>
        </label>
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search recipes…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {list.isLoading && <Loading />}
      {list.error && <ErrorState error={list.error} onRetry={list.refetch} />}
      {list.data?.length === 0 && <Empty title="No recipes found" />}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {list.data?.map((r) => (
          <Link
            key={r.id}
            to="/recipes/$id"
            params={{ id: r.id }}
            className="overflow-hidden rounded-xl border bg-card shadow-card transition hover:-translate-y-0.5"
          >
            <RecipeImage src={r.image_url} alt={r.title} className="aspect-video" />
            <div className="space-y-2 p-4">
              <div className="flex items-center justify-between">
                <MatchPill score={r.match.score} />
                <span className="text-xs text-muted-foreground">{r.category}</span>
              </div>
              <p className="font-display text-xl leading-tight">{r.title}</p>
              <p className="text-xs text-muted-foreground">
                {r.match.covered}/{r.match.total} ingredients covered
                {r.match.missing.length > 0 &&
                  ` · missing ${r.match.missing.slice(0, 3).join(", ")}${r.match.missing.length > 3 ? "…" : ""}`}
              </p>
              {r.match.expiring_used.length > 0 && (
                <p className="text-xs font-medium text-warning-foreground">
                  ⏳ Uses {r.match.expiring_used.join(", ")} before it expires
                </p>
              )}
            </div>
          </Link>
        ))}
      </div>
      <Dialog open={!!report} onOpenChange={(o) => !o && setReport(null)}>
        <DialogContent
          className="max-h-[calc(100dvh-2rem)] overflow-hidden"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            importButtonRef.current?.focus();
          }}
        >
          <DialogHeader className="pr-8">
            <DialogTitle className="font-display text-2xl">Import report</DialogTitle>
          </DialogHeader>
          {report && (
            <div
              aria-label="Import report results"
              className="max-h-[calc(100dvh-8rem)] overflow-y-auto overscroll-contain"
              role="region"
            >
              <div className="space-y-3 text-sm">
                <p>
                  {report.imported} new · {report.updated} updated · {report.total_recipes} recipes
                  total
                </p>
                {report.skipped.length > 0 && (
                  <>
                    <p className="font-medium">Skipped ({report.skipped.length})</p>
                    <ul className="space-y-1 text-muted-foreground" aria-label="Skipped recipes">
                      {report.skipped.map((s) => (
                        <li key={s.external_id}>
                          <span className="text-foreground">{s.title}</span> — {s.reason}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
