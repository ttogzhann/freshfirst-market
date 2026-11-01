import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getAuthService } from "@/services";
import type { AuthCredentials, AuthUser } from "@/services";
import { AuthContext, type AuthStatus } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const currentUser = useRef<AuthUser | null>(null);

  const applySession = useCallback(
    (nextUser: AuthUser | null) => {
      if (currentUser.current?.id !== nextUser?.id) queryClient.clear();
      currentUser.current = nextUser;
      setUser(nextUser);
      setStatus(nextUser ? "authenticated" : "anonymous");
    },
    [queryClient],
  );

  const restoreSession = useCallback(async () => {
    try {
      const session = await getAuthService().restoreSession();
      applySession(session.authenticated ? session.user : null);
    } catch {
      queryClient.clear();
      currentUser.current = null;
      setUser(null);
      setStatus("unavailable");
    }
  }, [applySession, queryClient]);

  useEffect(() => {
    const expireSession = () => applySession(null);
    window.addEventListener("freshfirst:unauthorized", expireSession);
    void restoreSession();
    return () => window.removeEventListener("freshfirst:unauthorized", expireSession);
  }, [applySession, restoreSession]);

  const authenticate = useCallback(
    async (operation: () => Promise<AuthUser>) => {
      const account = await operation();
      queryClient.clear();
      currentUser.current = account;
      setUser(account);
      setStatus("authenticated");
    },
    [queryClient],
  );

  const register = useCallback(
    (credentials: AuthCredentials) =>
      authenticate(() => getAuthService().registerAccount(credentials)),
    [authenticate],
  );
  const login = useCallback(
    (credentials: AuthCredentials) =>
      authenticate(() => getAuthService().loginAccount(credentials)),
    [authenticate],
  );
  const logout = useCallback(async () => {
    queryClient.clear();
    currentUser.current = null;
    setUser(null);
    setStatus("loading");
    try {
      await getAuthService().logoutAccount();
      setStatus("anonymous");
    } catch (error) {
      await restoreSession();
      throw error;
    }
  }, [queryClient, restoreSession]);

  return (
    <AuthContext.Provider value={{ status, user, restoreSession, register, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
