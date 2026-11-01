import { useEffect, type ReactNode } from "react";
import { AppShell } from "@/components/fresh/AppShell";
import { useAuth } from "./useAuth";
import { useNavigate, useRouterState } from "@tanstack/react-router";

export function AuthBoundary({ children }: { children: ReactNode }) {
  const { status, restoreSession } = useAuth();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const navigate = useNavigate();
  const isAuthPage = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    if (status === "anonymous" && !isAuthPage) {
      void navigate({ to: "/login", replace: true });
    } else if (status === "authenticated" && isAuthPage) {
      void navigate({ to: "/", replace: true });
    }
  }, [isAuthPage, navigate, status]);

  if (status === "loading" || (status === "anonymous" && !isAuthPage)) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        Restoring your session…
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
        <p role="alert">Your session could not be restored. Your saved data is hidden.</p>
        <button
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          onClick={() => void restoreSession()}
        >
          Try again
        </button>
      </div>
    );
  }

  if (status === "authenticated" && isAuthPage) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        Opening your account…
      </div>
    );
  }

  return status === "authenticated" ? <AppShell>{children}</AppShell> : children;
}
