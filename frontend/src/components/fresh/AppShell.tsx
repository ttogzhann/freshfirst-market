import { useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Leaf,
  Menu,
  ShoppingBasket,
  ChefHat,
  Refrigerator,
  ListChecks,
  X,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/pantry", label: "Pantry", icon: Refrigerator },
  { to: "/recipes", label: "Recipes", icon: ChefHat },
  { to: "/basket", label: "Basket", icon: ShoppingBasket },
  { to: "/shopping", label: "Shopping List", icon: ListChecks },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen md:flex">
      <header className="flex items-center justify-between bg-sidebar px-4 py-3 text-sidebar-foreground md:hidden">
        <Brand />
        <button aria-label="Toggle menu" onClick={() => setOpen((o) => !o)}>
          {open ? <X /> : <Menu />}
        </button>
      </header>
      <aside
        className={`${open ? "block" : "hidden"} bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:block md:h-screen md:w-64 md:shrink-0`}
      >
        <div className="hidden px-6 py-7 md:block">
          <Brand />
        </div>
        <nav className="flex flex-col gap-1 px-3 pb-6">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              activeOptions={{ exact: to === "/" }}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              activeProps={{ className: "!bg-sidebar-primary !text-sidebar-primary-foreground" }}
            >
              <Icon className="h-4 w-4" /> {label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 md:px-10 md:py-12">
        {children}
      </main>
    </div>
  );
}

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sidebar-primary text-sidebar-primary-foreground">
        <Leaf className="h-5 w-5" />
      </span>
      <span className="font-display text-xl font-semibold">FreshFirst</span>
    </Link>
  );
}
