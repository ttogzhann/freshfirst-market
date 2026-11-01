import { createFileRoute } from "@tanstack/react-router";
import { AuthForm } from "@/auth/AuthForm";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Sign in — FreshFirst" }] }),
  component: () => <AuthForm mode="login" />,
});
