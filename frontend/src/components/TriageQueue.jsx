// Darrel
// The open incidents ordered by priority, then severity, then age, with quick resolve. Sits under the log form on the Log & triage page.
import { useState } from "react";
import { AlertTriangle, CheckCheck, CheckCircle2, ClipboardList } from "lucide-react";
import { api } from "../api.js";
import IncidentTable from "./IncidentTable.jsx";

// One small number card above the queue.
function Count({ label, value, icon: Icon }) {
  return (
    <div className="card stat">
      <div className="stat-top">{label}<span className="stat-icon"><Icon size={15} /></span></div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export default function TriageQueue({ incidents, meta, onOpen, onChanged }) {
  const [priority, setPriority] = useState("");
  const [showResolved, setShowResolved] = useState(false);
  const [error, setError] = useState(null);

  const open = incidents.filter((i) => !i.resolved);
  const shown = incidents
    .filter((i) => showResolved || !i.resolved)
    .filter((i) => !priority || String(i.priority) === priority)
    .sort((a, b) => (a.resolved - b.resolved) || (a.priority - b.priority)
      || ((b.severity_estimate || 0) - (a.severity_estimate || 0)) || String(a.timestamp).localeCompare(String(b.timestamp)));

  async function resolve(incident) {
    try {
      await api.resolveIncident(incident.id, "");
      setError(null);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <section className="stats compact">
        <Count label="Open" value={open.length} icon={ClipboardList} />
        <Count label="Urgent open (P1)" value={open.filter((i) => i.priority === 1).length} icon={AlertTriangle} />
        <Count label="High open (P2)" value={open.filter((i) => i.priority === 2).length} icon={AlertTriangle} />
        <Count label="Resolved" value={incidents.length - open.length} icon={CheckCheck} />
      </section>
      <div className="card">
        <div className="card-title">
          <h3>Triage queue</h3>
          <span>{shown.length} shown · most urgent first</span>
        </div>
        <div className="toolbar">
          <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">All priorities</option>
            {Object.entries(meta.priority_levels || {}).map(([id, name]) => <option key={id} value={id}>P{id} {name}</option>)}
          </select>
          <button className={`btn ${showResolved ? "selected" : ""}`} onClick={() => setShowResolved(!showResolved)}>
            Show resolved
          </button>
        </div>
        {error && <div className="alert error">{error}</div>}
        <IncidentTable incidents={shown} meta={meta} onOpen={onOpen}
                       onAction={(incident) => !incident.resolved && (
                         <button className="btn small" onClick={(e) => { e.stopPropagation(); resolve(incident); }}>
                           <CheckCircle2 size={13} /> Resolve
                         </button>
                       )} />
      </div>
    </>
  );
}
