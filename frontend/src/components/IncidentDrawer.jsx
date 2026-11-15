// Lennart
// Only the re-analyse part of the drawer. The rest of this file (report, edit form, version history, delete)
// belongs to Sufi's card and is added when her pull request is merged.
import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../api.js";

export default function IncidentDrawer({ incident, onChanged }) {
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  // Asks the AI again about the incident as saved; a new version is saved, the old one stays in the history.
  async function reanalyse() {
    setBusy(true);
    try {
      await api.reanalyseIncident(incident.id);
      onChanged();
    } catch (err) {
      const kept = err.body?.kept_version;
      setNotice(kept ? `${err.message} The old version (version ${kept}) was kept.` : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button className="btn" onClick={reanalyse} disabled={busy} title="Ask the AI again with the same details">
        <RefreshCw size={15} /> {busy ? "Working..." : "Re-analyse"}
      </button>
      {notice && <div className="alert info">{notice}</div>}
    </div>
  );
}
