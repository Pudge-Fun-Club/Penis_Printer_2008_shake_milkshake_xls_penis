import { useI18n } from "../i18n";

/** Compact printer/backend status indicator shown in the app header. */
export default function StatusPill({ status }: { status: any }) {
  const { t } = useI18n();
  if (!status) return <span className="pill off">{t("status.backendOffline")}</span>;
  if (!status.configured)
    return <span className="pill warn">{t("status.octoUnconfigured")}</span>;
  if (!status.online) return <span className="pill off">{t("status.octoOffline")}</span>;
  const state = status.printer?.state?.text ?? status.connection?.state ?? t("status.connected");
  const printing = status.job?.state?.toLowerCase?.().includes("printing");
  return (
    <span className={`pill ${printing ? "busy" : "ok"}`}>
      ● {state}
    </span>
  );
}
