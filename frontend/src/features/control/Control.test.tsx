// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider } from "../../components/Toasts";
import { I18nProvider } from "../../i18n";
import Control from "./Control";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function app(failure = false) {
  let selected = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/printer/backends") return Response.json([
      { id: "octoprint", configured: false, online: false, active: !selected },
      ...(selected ? [{ id: "serial", configured: true, online: false, active: true }] : []),
    ]);
    if (url === "/api/printer/backend" && JSON.parse(String(init?.body)).id === "serial") {
      if (failure) return Response.json({ detail: "USB access denied" }, { status: 403 });
      selected = true;
      return Response.json({ ok: true, active: "serial" });
    }
    return Response.json([]);
  }));
  render(<I18nProvider><ToastProvider><Control status={{ backend: "octoprint", online: false }} onAction={() => {}} /></ToastProvider></I18nProvider>);
}

it("offers USB on a default install and activates it without OctoPrint keys", async () => {
  app();
  fireEvent.click(await screen.findByRole("button", { name: "Connect via USB" }));
  expect(await screen.findByText("active")).toBeTruthy();
});

it("shows a connection failure instead of silently swallowing it", async () => {
  app(true);
  fireEvent.click(await screen.findByRole("button", { name: "Connect via USB" }));
  expect((await screen.findByRole("alert")).textContent).toContain("USB access denied");
});
