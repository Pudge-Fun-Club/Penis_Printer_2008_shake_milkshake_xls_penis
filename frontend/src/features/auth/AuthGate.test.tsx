// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider } from "../../components/Toasts";
import { I18nProvider } from "../../i18n";
import AuthGate from "./AuthGate";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
beforeEach(() => localStorage.clear());

function app() {
  render(<I18nProvider><ToastProvider><AuthGate><p>Printer controls</p></AuthGate></ToastProvider></I18nProvider>);
}

function authServer(configured: boolean) {
  let authenticated = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/session") {
      return Response.json({ configured, authenticated, username: configured ? "admin" : null });
    }
    if (url === (configured ? "/api/auth/login" : "/api/auth/setup")) {
      const body = JSON.parse(String(init?.body));
      if (body.username !== "admin" || body.password !== "supersecret12" || Object.keys(body).length !== 2) {
        return Response.json({ detail: "Invalid credentials" }, { status: 401 });
      }
      configured = true;
      authenticated = true;
      return Response.json({ expires: 2000000000 });
    }
    return Response.json({ detail: "Unknown auth step" }, { status: 404 });
  }));
}

it("opens the app after creating an admin with username and password", async () => {
  authServer(false);
  app();
  const password = await screen.findByLabelText("Password");
  fireEvent.change(password, { target: { value: "supersecret12" } });
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Printer controls")).toBeTruthy();
});

it("logs into an existing account using only a password", async () => {
  authServer(true);
  app();
  const password = await screen.findByLabelText("Password");
  expect(screen.queryByText("Authenticator code")).toBeNull();
  fireEvent.change(password, { target: { value: "supersecret12" } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByText("Printer controls")).toBeTruthy();
});
