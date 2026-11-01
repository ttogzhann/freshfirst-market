import type { ReactNode } from "react";
import { AuthContext, type AuthContextValue } from "@/auth/AuthContext";

const authenticatedTestSession: AuthContextValue = {
  status: "authenticated",
  user: { id: "test-account", email: "test@example.com" },
  restoreSession: async () => {},
  register: async () => {},
  login: async () => {},
  logout: async () => {},
};

export function AuthenticatedTestProvider({ children }: { children: ReactNode }) {
  return <AuthContext.Provider value={authenticatedTestSession}>{children}</AuthContext.Provider>;
}
