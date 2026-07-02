import { useEffect, useState, type ReactNode } from "react";
import { api, type AuthSession } from "../../api";
import { useI18n } from "../../i18n";
import AuthShell from "./AuthShell";
import LoginForm from "./LoginForm";
import SetupForm from "./SetupForm";

/** Renders children only for an authenticated admin; otherwise the setup or
 * login flow (or a loading/error shell while the session is unknown). */
export default function AuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [session, setSession] = useState<AuthSession | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = () =>
    api
      .authSession()
      .then((s) => {
        setSession(s);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message ?? e)));

  useEffect(() => {
    refresh();
  }, []);

  if (err) return <AuthShell><div className="banner err">{err}</div></AuthShell>;
  if (!session) return <AuthShell><p className="muted">{t("common.loading")}</p></AuthShell>;
  if (!session.configured) return <SetupForm onDone={refresh} />;
  if (!session.authenticated) return <LoginForm username={session.username ?? ""} onDone={refresh} />;
  return <>{children}</>;
}
