// Darrel
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { LogIn, LogOut, X } from "lucide-react";
import { api } from "../api.js";

// The sidebar's supervisor login. There is no sign-up: only the accounts the server whitelists can log in.
// Logged in, the dashboard may resolve, reopen, prioritise, edit, re-analyse and delete incidents and change the site plan.
export default function SupervisorLogin() {
  const [user, setUser] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Asks the server who the saved token belongs to (it may have run out since the last visit).
    function check() {
      if (!api.hasLogin()) {
        setUser(null);
        return;
      }
      api.session().then((s) => setUser(s.username)).catch(() => setUser(null));
    }
    check();
    window.addEventListener("supervisor-change", check);
    return () => window.removeEventListener("supervisor-change", check);
  }, []);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { username } = await api.login(form.username, form.password);
      setUser(username);
      setOpen(false);
      setForm({ username: "", password: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function close() {
    setOpen(false);
    setError(null);
  }

  const dialog = open && (
    <div className="login-backdrop" onClick={close}>
      <form className="login-card" role="dialog" aria-modal="true" aria-labelledby="login-title"
            onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="login-head">
          <strong id="login-title">Supervisor login</strong>
          <button type="button" className="icon-btn" aria-label="Close" onClick={close}><X size={18} /></button>
        </div>
        <p className="muted small">
          Resolving, prioritising, editing and deleting incidents needs a supervisor account. Anyone can still log a new incident.
        </p>
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
        <button className="btn primary" type="submit" disabled={busy}>{busy ? "Logging in..." : "Log in"}</button>
      </form>
    </div>
  );

  return (
    <>
      {user ? (
        <button className="nav-item" title={`Logged in as ${user}. Log out`} onClick={() => api.logout()}>
          <LogOut size={17} /> <span className="nav-text">Log out ({user})</span>
        </button>
      ) : (
        <button className="nav-item" title="Supervisor login" onClick={() => setOpen(true)}>
          <LogIn size={17} /> <span className="nav-text">Supervisor login</span>
        </button>
      )}
      {/* On phones the sidebar slides in with a transform, so the dialog is drawn on the page body instead. */}
      {dialog && createPortal(dialog, document.body)}
    </>
  );
}
