import { useEffect, useState } from "react";
import { api } from "../../api";
import { useToasts } from "../../components/Toasts";
import { useI18n } from "../../i18n";
import AuthShell from "./AuthShell";

export default function LoginForm({ username: initialUsername, onDone }: { username: string; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToasts();
  const [username, setUsername] = useState(initialUsername);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = () => {
    setBusy(true);
    setErr(null);
    api
      .authLogin(username, password, useRecovery ? "" : code, useRecovery ? code : "")
      .then(onDone)
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setBusy(false));
  };

  useEffect(() => {
    if (err) toast.error(err);
  }, [err, toast]);

  return (
    <AuthShell>
      <h2>{t("auth.loginTitle")}</h2>
      <div className="auth-form">
        <label>{t("auth.username")}<input value={username} onChange={(e) => setUsername(e.target.value)} /></label>
        <label>{t("auth.password")}<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <label>{useRecovery ? t("auth.recoveryCode") : t("auth.totpCode")}<input inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <label className="checkline"><input type="checkbox" checked={useRecovery} onChange={(e) => setUseRecovery(e.target.checked)} />{t("auth.useRecovery")}</label>
        <button className="primary" disabled={busy} onClick={submit}>{t("auth.login")}</button>
      </div>
    </AuthShell>
  );
}
