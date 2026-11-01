import { createFileRoute } from "@tanstack/react-router";
import { AuthForm } from "@/auth/AuthForm";

export const Route = createFileRoute("/register")({
  head: () => ({ meta: [{ title: "Create account — FreshFirst" }] }),
  component: () => <AuthForm mode="register" />,
});
