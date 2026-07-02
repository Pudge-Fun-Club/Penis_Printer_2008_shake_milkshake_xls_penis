import { type ReactNode } from "react";
import { useI18n } from "../../i18n";

/** Centered card layout shared by the setup, login and error screens. */
export default function AuthShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="auth-page">
      <section className="card auth-card">
        <h1><span className="pen">✎</span> GCodeScribe</h1>
        {location.protocol === "http:" && !["localhost", "127.0.0.1"].includes(location.hostname) && (
          <div className="banner warn">{t("auth.httpWarning")}</div>
        )}
        {children}
      </section>
    </div>
  );
}
