import { useEffect, useState } from "react";
import { api, type AuthSetupStart } from "../../api";
import { useToasts } from "../../components/Toasts";
import { useI18n } from "../../i18n";
import AuthShell from "./AuthShell";

/** First-run admin setup: credentials, TOTP enrolment, recovery codes. */
export default function SetupForm({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToasts();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<AuthSetupStart | null>(null);
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const start = () => {
    setBusy(true);
    setErr(null);
    api.authSetupStart(username, password).then(setSetup).catch((e) => setErr(String(e.message ?? e))).finally(() => setBusy(false));
  };
  const finish = () => {
    if (!setup) return;
    setBusy(true);
    setErr(null);
    api.authSetupFinish(setup.setupId, code).then((r) => setRecovery(r.recoveryCodes)).catch((e) => setErr(String(e.message ?? e))).finally(() => setBusy(false));
  };

  useEffect(() => {
    if (err) toast.error(err);
  }, [err, toast]);

  if (recovery) {
    return (
      <AuthShell>
        <h2>{t("auth.recoveryTitle")}</h2>
        <p className="muted">{t("auth.recoveryHint")}</p>
        <ul className="recovery-list">{recovery.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
        <button className="primary" onClick={onDone}>{t("common.next")}</button>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <h2>{t("auth.setupTitle")}</h2>
      <p className="muted">{t("auth.setupHint")}</p>
      {!setup ? (
        <div className="auth-form">
          <label>{t("auth.username")}<input value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <label>{t("auth.password")}<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <button className="primary" disabled={busy} onClick={start}>{t("auth.startSetup")}</button>
        </div>
      ) : (
        <div className="auth-form">
          <p className="muted">{t("auth.secretHint")}</p>
          <label>{t("auth.secretLabel")}<input readOnly value={setup.totpSecret} onFocus={(e) => e.currentTarget.select()} /></label>
          <label>{t("auth.otpauthLabel")}<textarea readOnly value={setup.otpauthUri} onFocus={(e) => e.currentTarget.select()} /></label>
          <label>{t("auth.totpCode")}<input inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} /></label>
          <button className="primary" disabled={busy} onClick={finish}>{t("auth.finishSetup")}</button>
        </div>
      )}
    </AuthShell>
  );
}
