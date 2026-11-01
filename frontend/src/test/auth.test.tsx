import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthBoundary } from "@/auth/AuthBoundary";
import { AuthForm } from "@/auth/AuthForm";
import { AuthProvider } from "@/auth/AuthProvider";
import { Dashboard } from "@/routes/index";
import { setService } from "@/services";
import { createMockService } from "@/services/mock/mockService";
import type { AuthService, AuthUser, FreshService } from "@/services";

const account: AuthUser = { id: "acct-1", email: "person@example.com" };

function TestRoot() {
  const { queryClient } = rootRoute.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthBoundary>
          <Outlet />
        </AuthBoundary>
      </AuthProvider>
    </QueryClientProvider>
  );
}

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: TestRoot,
});
const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <p>Good to see you</p>,
});
const privateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/private",
  component: Dashboard,
});
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: () => <AuthForm mode="login" />,
});
const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: () => <AuthForm mode="register" />,
});
const testRouteTree = rootRoute.addChildren([homeRoute, privateRoute, loginRoute, registerRoute]);

function authService(
  restoreSession: AuthService["restoreSession"] = async () => ({
    authenticated: false,
    user: null,
  }),
) {
  return Object.assign(createMockService(), {
    restoreSession,
    registerAccount: vi.fn(async () => account),
    loginAccount: vi.fn(async () => account),
    logoutAccount: vi.fn(async () => undefined),
  });
}

async function renderAt(
  path: string,
  service: FreshService & AuthService,
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  setService(service);
  const router = createRouter({
    routeTree: testRouteTree,
    context: { queryClient },
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  await act(async () => {
    render(<RouterProvider router={router} />);
    await Promise.resolve();
  });
  return { queryClient, router };
}

afterEach(() => {
  setService(createMockService());
});

describe("authentication screens and route state", () => {
  it("offers registration and login forms with bounded, non-persisted password fields", async () => {
    const service = authService();
    await renderAt("/login", service);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeVisible();
    const email = screen.getByLabelText("Email") as HTMLInputElement;
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(email.maxLength).toBe(254);
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password.minLength).toBe(12);
    expect(password.maxLength).toBe(128);

    fireEvent.click(screen.getByRole("link", { name: "Create an account" }));
    expect(await screen.findByRole("heading", { name: "Create your account" })).toBeVisible();
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
  });

  it("waits for session restoration before showing private routes", async () => {
    let resolveSession!: (session: { authenticated: boolean; user: AuthUser | null }) => void;
    const restore = vi.fn(
      () =>
        new Promise<{ authenticated: boolean; user: AuthUser | null }>((resolve) => {
          resolveSession = resolve;
        }),
    );
    const service = authService(restore);
    const getDashboard = vi.spyOn(service, "getDashboard");
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["dashboard"], {
      total_items: 999,
      expiring_soon: 999,
      expired: 999,
      recommendations: [],
      recent_history: [],
    });

    await renderAt("/private", service, queryClient);

    expect(await screen.findByRole("status")).toHaveTextContent("Restoring your session");
    expect(screen.queryByText("Good to see you")).not.toBeInTheDocument();
    expect(screen.queryByText("999")).not.toBeInTheDocument();
    expect(getDashboard).not.toHaveBeenCalled();

    await act(async () => resolveSession({ authenticated: false, user: null }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeVisible();
    expect(screen.queryByText("999")).not.toBeInTheDocument();
    expect(getDashboard).not.toHaveBeenCalled();
  });

  it("starts the dashboard request only after authenticated session restoration", async () => {
    let resolveSession!: (session: { authenticated: boolean; user: AuthUser | null }) => void;
    const restore = vi.fn(
      () =>
        new Promise<{ authenticated: boolean; user: AuthUser | null }>((resolve) => {
          resolveSession = resolve;
        }),
    );
    const service = authService(restore);
    const getDashboard = vi.spyOn(service, "getDashboard");
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["dashboard"], {
      total_items: 999,
      expiring_soon: 999,
      expired: 999,
      recommendations: [],
      recent_history: [],
    });

    await renderAt("/private", service, queryClient);
    expect(await screen.findByRole("status")).toHaveTextContent("Restoring your session");
    expect(screen.queryByText("999")).not.toBeInTheDocument();
    expect(getDashboard).not.toHaveBeenCalled();

    await act(async () => resolveSession({ authenticated: true, user: account }));
    expect(await screen.findByText("Good to see you")).toBeVisible();
    await waitFor(() => expect(getDashboard).toHaveBeenCalledOnce());
    expect(screen.queryByText("999")).not.toBeInTheDocument();
    expect(queryClient.getQueryData(["dashboard"])).not.toMatchObject({ total_items: 999 });
  });

  it("restores the account, clears cached data, and clears it again on logout", async () => {
    const service = authService(async () => ({ authenticated: true, user: account }));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["pantry"], [{ id: "old-account-private-row" }]);
    const rendered = await renderAt("/", service, queryClient);

    expect(await screen.findByText("Good to see you")).toBeVisible();
    expect(await screen.findByText(account.email)).toBeVisible();
    expect(queryClient.getQueryData(["pantry"])).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeVisible();
    await waitFor(() => expect(service.logoutAccount).toHaveBeenCalledOnce());
    expect(queryClient.getQueryData(["pantry"])).toBeUndefined();
    expect(rendered.router.state.location.pathname).toBe("/login");
  });

  it("registers without retaining the password in the form or browser storage", async () => {
    const service = authService();
    await renderAt("/register", service);

    const email = await screen.findByLabelText("Email");
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    fireEvent.change(email, { target: { value: "new@example.com" } });
    fireEvent.change(password, { target: { value: "a long enough test password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(service.registerAccount).toHaveBeenCalledWith({
        email: "new@example.com",
        password: "a long enough test password",
      }),
    );
    expect(await screen.findByText("Good to see you")).toBeVisible();
    expect(password.value).toBe("");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("submits login credentials and enters the private application", async () => {
    const service = authService();
    await renderAt("/login", service);

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    fireEvent.change(password, { target: { value: "a long enough test password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(service.loginAccount).toHaveBeenCalledWith({
        email: "person@example.com",
        password: "a long enough test password",
      }),
    );
    expect(await screen.findByText("Good to see you")).toBeVisible();
    expect(password.value).toBe("");
  });
});
