// Darrel
import { useState } from "react";
import { LogIn } from "lucide-react";
import { api } from "../api.js";

// The page shown before the dashboard. There is no sign-up: only the accounts the server whitelists can log in.
// onLogin(username) is called once the server accepts the name and password.
export default function SupervisorLogin({ onLogin, notice }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { username } = await api.login(form.username, form.password);
      onLogin(username);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit} aria-labelledby="login-title">
        <div className="brand login-brand">
          <div className="brand-logo"><span /></div>
          <div>
            <div className="brand-name">Workplace</div>
            <div className="brand-sub">Incident triage</div>
          </div>
        </div>
        <h1 id="login-title" className="login-title">Log in</h1>
        <p className="muted small">Use the account your team gave you. New accounts cannot be created here.</p>
        {notice && !error && <div className="alert info">{notice}</div>}
        {error && <div className="alert error">{error}</div>}
        <div className="field">
          <label htmlFor="login-username">Username</label>
          <input id="login-username" className="input" autoComplete="username" required autoFocus maxLength={50}
                 value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="login-password">Password</label>
          <input id="login-password" className="input" type="password" autoComplete="current-password" required
                 maxLength={100} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <button className="btn primary" type="submit" disabled={busy}>
          <LogIn size={15} /> {busy ? "Logging in..." : "Log in"}
        </button>
      </form>
    </div>
  );
}
