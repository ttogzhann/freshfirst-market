import { createContext } from "react";
import type { AuthCredentials, AuthUser } from "@/services";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "unavailable";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  restoreSession(): Promise<void>;
  register(credentials: AuthCredentials): Promise<void>;
  login(credentials: AuthCredentials): Promise<void>;
  logout(): Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
