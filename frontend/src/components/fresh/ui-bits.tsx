import type { ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { errorMessage } from "@/hooks/use-fresh";
import type { ExpiryStatus } from "@/services";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-4xl font-semibold text-foreground">{title}</h1>
        {subtitle && <p className="mt-1 text-muted-foreground">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-12 text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6">
      <div className="flex items-center gap-2 font-medium text-destructive">
        <AlertTriangle className="h-4 w-4" /> {errorMessage(error)}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed bg-card/50 p-10 text-center">
      <p className="font-display text-xl">{title}</p>
      {children && <div className="mt-2 text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

export function ExpiryBadge({ status, days }: { status: ExpiryStatus; days: number }) {
  if (status === "expired") return <Badge variant="destructive">Expired</Badge>;
  if (status === "expiring")
    return (
      <Badge className="bg-warning text-warning-foreground hover:bg-warning">
        {days === 0 ? "Expires today" : `${days}d left`}
      </Badge>
    );
  return <Badge variant="secondary">{days}d left</Badge>;
}

export function MatchPill({ score }: { score: number }) {
  const tone =
    score >= 80
      ? "bg-primary text-primary-foreground"
      : score >= 50
        ? "bg-accent text-accent-foreground"
        : "bg-muted text-muted-foreground";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${tone}`}>{score}% match</span>
  );
}

export function RecipeImage({
  src,
  alt,
  className = "",
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  return (
    <div className={`relative overflow-hidden bg-hero ${className}`}>
      <span className="absolute inset-0 flex items-center justify-center font-display text-4xl text-primary-foreground/80">
        {alt.charAt(0)}
      </span>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        className="relative h-full w-full object-cover"
        onError={(e) => (e.currentTarget.style.display = "none")}
      />
    </div>
  );
}
