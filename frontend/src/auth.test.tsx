import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { passwordStrength } from "./pages/Auth";
import { SIGNED_IN, SIGNED_OUT, callsTo, mockApi, renderAt } from "./testUtils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const type = (label: RegExp | string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("Sign up", () => {
  it("validates on the client with clear inline messages and sends nothing", async () => {
    const fetchFn = mockApi();
    renderAt("/signup");
    await screen.findByRole("heading", { name: "Create your account" });
    type("Email", "not-an-email");
    type(/^Password/, "short");
    type("Confirm password", "different");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Tell us what to call you.")).toBeTruthy();
    expect(screen.getByText("Enter an email address like name@example.com.")).toBeTruthy();
    expect(screen.getByText("The two passwords don't match.")).toBeTruthy();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(callsTo(fetchFn, "POST /api/auth/signup")).toEqual([]);
  });

  it("shows the server's message for an email that's taken", async () => {
    mockApi({
      "POST /api/auth/signup": {
        status: 409,
        body: {
          detail: "That email is already registered.",
          fields: { email: "That email is already registered. Try signing in instead." },
        },
      },
    });
    renderAt("/signup");
    await screen.findByRole("heading", { name: "Create your account" });
    type("Name", "Ravi");
    type("Email", "ravi@example.com");
    type(/^Password/, "correct horse battery");
    type("Confirm password", "correct horse battery");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("That email is already registered. Try signing in instead.")).toBeTruthy();
  });

  it("shows a live password strength hint", async () => {
    mockApi();
    renderAt("/signup");
    await screen.findByRole("heading", { name: "Create your account" });
    type(/^Password/, "abc");
    expect(screen.getByText("7 more characters needed.")).toBeTruthy();
    type(/^Password/, "correct horse battery staple");
    expect(screen.getByText("Strong password.")).toBeTruthy();
  });

  it("offers GitHub sign-in that keeps where you were going", async () => {
    mockApi();
    renderAt("/signup?next=%2Freview%2F5");
    const gh = await screen.findByRole("link", { name: /Continue with GitHub/ });
    expect(gh.getAttribute("href")).toBe("/api/auth/github/start?next=%2Freview%2F5");
  });
});

describe("Log in", () => {
  it("signs in and goes to the page that asked for it", async () => {
    const fetchFn = mockApi({
      "GET /api/auth/me": [SIGNED_OUT, SIGNED_IN],
      "POST /api/auth/login": { user: SIGNED_IN.user },
      "GET /api/runs": { runs: [], runs_this_month: 0, spend_this_month_usd: 0, spend_cap_usd: 10 },
    });
    renderAt("/login?next=%2Fdashboard");
    await screen.findByRole("heading", { name: "Welcome back" });
    type("Email", "ravi@example.com");
    type(/^Password/, "correct horse battery");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeTruthy();
    expect(callsTo(fetchFn, "POST /api/auth/login")).toEqual([
      { email: "ravi@example.com", password: "correct horse battery" },
    ]);
  });

  it("shows a wrong-password message next to the field", async () => {
    mockApi({
      "POST /api/auth/login": {
        status: 401,
        body: { detail: "Email or password is incorrect.", fields: { password: "Email or password is incorrect." } },
      },
    });
    renderAt("/login");
    await screen.findByRole("heading", { name: "Welcome back" });
    type("Email", "ravi@example.com");
    type(/^Password/, "nope nope nope");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Email or password is incorrect.")).toBeTruthy();
  });

  it("explains rate limiting", async () => {
    mockApi({ "POST /api/auth/login": { status: 429, body: { detail: "Too many attempts. Wait a few minutes and try again." } } });
    renderAt("/login");
    await screen.findByRole("heading", { name: "Welcome back" });
    type("Email", "ravi@example.com");
    type(/^Password/, "whatever123");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Too many attempts. Wait a few minutes and try again.")).toBeTruthy();
  });

  it("explains a failed GitHub sign-in", async () => {
    mockApi();
    renderAt("/login?error=github_failed");
    expect(await screen.findByText(/GitHub sign-in didn't complete/)).toBeTruthy();
  });

  it("has a forgot-password placeholder", async () => {
    mockApi();
    renderAt("/login");
    fireEvent.click(await screen.findByRole("link", { name: "Forgot password?" }));
    expect(await screen.findByText("Password reset isn't available yet")).toBeTruthy();
  });

  it("sends signed-out visitors from the dashboard to login and back", async () => {
    mockApi();
    renderAt("/dashboard");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy();
  });

  it("skips the login page when already signed in", async () => {
    mockApi({
      "GET /api/auth/me": SIGNED_IN,
      "GET /api/runs": { runs: [], runs_this_month: 0, spend_this_month_usd: 0, spend_cap_usd: 10 },
    });
    renderAt("/login");
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeTruthy();
  });
});

describe("passwordStrength", () => {
  it("matches the server rule", () => {
    expect(passwordStrength("").level).toBe(0);
    expect(passwordStrength("short").level).toBe(1);
    expect(passwordStrength("aaaaaaaaaaaa").level).toBe(1);
    expect(passwordStrength("ravi@example.com", "ravi@example.com").level).toBe(1);
    expect(passwordStrength("lowercaseonly").level).toBe(2);
    expect(passwordStrength("Correct-Horse-1").level).toBe(3);
  });
});
