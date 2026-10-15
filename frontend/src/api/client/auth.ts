import { req } from "./req";
import type { AuthSession, AuthLoginResult } from "../types/auth";

export const authClient = {
  health: () => req<{ ok: boolean; desktop: boolean }>("/api/health"),
  authSession: () => req<AuthSession>("/api/auth/session"),
  authSetup: (username: string, password: string) =>
    req<AuthLoginResult>("/api/auth/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  authLogin: (username: string, password: string) =>
    req<AuthLoginResult>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  authLogout: () => req<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
};
