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
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = () => {
    setBusy(true);
    setErr(null);
    api
      .authLogin(username, password)
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
      <form className="auth-form" onSubmit={e => { e.preventDefault(); if (!busy) submit(); }}>
        <label>{t("auth.username")}<input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} /></label>
        <label>{t("auth.password")}<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label>
        <button className="primary" disabled={busy} type="submit">{t("auth.login")}</button>
      </form>
    </AuthShell>
  );
}
