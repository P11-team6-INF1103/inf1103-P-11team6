// Darrel
// Priority and resolved status of one incident. Anyone can change them.
import { useState } from "react";
import { CheckCircle2, RotateCcw } from "lucide-react";
import { api } from "../api.js";
import { formatDate } from "../labels.js";
import { PriorityPill, StatusPill } from "./Pills.jsx";

export default function WorkflowPanel({ incident, meta, onChanged }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await action());
      setNote("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  const levels = meta.priority_levels || {};
  return (
    <div className="card flat workflow">
      <div className="card-title">
        <h3>Status and priority</h3>
      </div>
      <div className="workflow-row">
        <PriorityPill incident={incident} />
        <StatusPill incident={incident} />
      </div>

      {incident.resolved && (
        <p className="muted">
          Resolved on {formatDate(incident.resolved_at)}
          {incident.resolution_note && <>: “{incident.resolution_note}”</>}
        </p>
      )}
      {error && <div className="alert error">{error}</div>}

      <>
          <div className="field">
            <label>Priority {incident.priority_source === "auto" && "(suggested from the severity)"}</label>
            <select className="input" value={incident.priority_source === "manual" ? incident.priority : "auto"} disabled={busy}
                    onChange={(e) => run(() => api.setPriority(incident.id, e.target.value === "auto" ? null : Number(e.target.value)))}>
              <option value="auto">Automatic (P{incident.priority_source === "auto" ? incident.priority : "?"})</option>
              {Object.entries(levels).map(([level, name]) => <option key={level} value={level}>P{level} {name}</option>)}
            </select>
          </div>
          {incident.resolved ? (
            <button className="btn" disabled={busy} onClick={() => run(() => api.reopenIncident(incident.id))}>
              <RotateCcw size={14} /> Reopen
            </button>
          ) : (
            <>
              <div className="field">
                <label>Resolution note (optional)</label>
                <input className="input" maxLength={500} value={note} placeholder="What was done to fix it?"
                       onChange={(e) => setNote(e.target.value)} />
              </div>
              <button className="btn primary" disabled={busy} onClick={() => run(() => api.resolveIncident(incident.id, note))}>
                <CheckCircle2 size={14} /> Mark as resolved
              </button>
            </>
          )}
      </>
    </div>
  );
}
