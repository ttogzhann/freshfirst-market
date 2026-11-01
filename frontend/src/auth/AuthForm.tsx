import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { errorMessage } from "@/hooks/use-fresh";
import { useAuth } from "./useAuth";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setError(null);
    setSubmitting(true);
    try {
      const credentials = {
        email: String(values.get("email") ?? ""),
        password: String(values.get("password") ?? ""),
      };
      if (isRegister) await register(credentials);
      else await login(credentials);
      await navigate({ to: "/", replace: true });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      const password = form.elements.namedItem("password");
      if (password instanceof HTMLInputElement) password.value = "";
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border bg-card p-7 shadow-card sm:p-9">
        <Link to="/" className="font-display text-2xl font-semibold text-primary">
          FreshFirst
        </Link>
        <h1 className="mt-7 font-display text-3xl font-semibold">
          {isRegister ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {isRegister
            ? "Save your pantry and cooking progress securely."
            : "Sign in to see your saved pantry and recipes."}
        </p>
        <form className="mt-7 space-y-5" onSubmit={(event) => void submit(event)}>
          <label className="block space-y-2 text-sm font-medium">
            Email
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2.5 font-normal"
              type="email"
              name="email"
              autoComplete="email"
              required
              minLength={3}
              maxLength={254}
            />
          </label>
          <label className="block space-y-2 text-sm font-medium">
            Password
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2.5 font-normal"
              type="password"
              name="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              required
              minLength={12}
              maxLength={128}
            />
          </label>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <button
            className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={submitting}
          >
            {submitting
              ? isRegister
                ? "Creating account…"
                : "Signing in…"
              : isRegister
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {isRegister ? "Already have an account?" : "New to FreshFirst?"}{" "}
          <Link
            to={isRegister ? "/login" : "/register"}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {isRegister ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
