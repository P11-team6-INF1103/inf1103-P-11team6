// Sufi

// Slides in from the right with the full report, the edit form and the version history.
// Delete asks for a second click to confirm.
import { useEffect, useState } from "react";
import { Pencil, RefreshCw, Trash2, X } from "lucide-react";
import { api } from "../api.js";
import IncidentForm from "./IncidentForm.jsx";
import IncidentReport from "./IncidentReport.jsx";
import VersionCompare from "./VersionCompare.jsx";
import VersionHistory from "./VersionHistory.jsx";
import WorkflowPanel from "./WorkflowPanel.jsx";

export default function IncidentDrawer({ incident: summary, initialMode = "report", meta, onClose, onDelete, onChanged }) {
  const [incident, setIncident] = useState(summary);
  const [mode, setMode] = useState(initialMode);
  const [change, setChange] = useState(null);
  const [notice, setNotice] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  // The list has no history, so load the full incident once the drawer opens.
  useEffect(() => {
    api.incident(summary.id).then(setIncident).catch(() => {});
  }, [summary.id]);

  async function handleDelete() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setBusy(true);
    await onDelete(incident);
    setBusy(false);
  }

  // A new version was saved: show it with the old insight beside it.
  function showChange(saved) {
    setIncident(saved);
    setChange({ previous: saved.history[saved.history.length - 1], current: saved });
    setNotice(null);
    setMode("report");
    onChanged();
  }

  async function saveEdit(data) {
    let saved;
    try {
      saved = await api.editIncident(incident.id, data);
    } catch (err) {
      const kept = err.body?.kept_version;
      throw new Error(kept ? `${err.message} The old version (version ${kept}) was kept.` : err.message);
    }
    if (saved.status === "unchanged") {
      setNotice("Nothing was changed, so the AI was not run again.");
      setMode("report");
      return;
    }
    showChange(saved);
  }

  async function revert(version) {
    try {
      showChange(await api.revertIncident(incident.id, version));
    } catch (err) {
      setNotice(err.message);
      setMode("report");
    }
  }

//Lennart
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

// Sufi
  const tabs = [["report", "Report"], ["edit", "Edit"], ["history", `History (${incident.version || 1})`]];

  return (
    <div className="backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-actions">
          <button className="btn" onClick={onClose}><X size={15} /> Close</button>
          <button className="btn" onClick={reanalyse} disabled={busy} title="Ask the AI again with the same details">
            <RefreshCw size={15} /> {busy ? "Working..." : "Re-analyse"}
          </button>
          <button className="btn danger" onClick={handleDelete} disabled={busy}>
            <Trash2 size={15} /> {confirming ? "Click again to delete" : "Delete"}
          </button>
        </div>
        <div className="tabs">
          {tabs.map(([id, label]) => (
            <button key={id} className={`btn small ${mode === id ? "selected" : ""}`} onClick={() => { setMode(id); setNotice(null); }}>
              {id === "edit" && <Pencil size={13} />} {label}
            </button>
          ))}
        </div>
        {notice && <div className="alert info">{notice}</div>}

        {mode === "edit" && (
          <IncidentForm key={incident.version} mode="edit" incident={incident} onSubmit={saveEdit} onCancel={() => setMode("report")} />
        )}
        {mode === "history" && incident.history && <VersionHistory incident={incident} meta={meta} onRevert={revert} />}
        {mode === "report" && (
          <>
            {change && (
              <div className="card flat change-banner">
                <div className="card-title">
                  <h3>Updated to version {change.current.version}</h3>
                  <span>old → new</span>
                </div>
                <VersionCompare previous={change.previous} current={change.current} meta={meta} />
              </div>
            )}
            <WorkflowPanel incident={incident} meta={meta}
                           onChanged={(saved) => { setIncident({ ...incident, ...saved }); onChanged(saved); }} />
            <IncidentReport incident={incident} meta={meta} />
          </>
        )}
      </div>
    </div>
  );
}
