// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
// Every saved version of one incident, newest first; "revert" copies an older one in as the newest.
import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "../api.js";
import { formatDate } from "../labels.js";
import { OutcomePill, SeverityPill } from "./Pills.jsx";
import VersionCompare from "./VersionCompare.jsx";

export default function VersionHistory({ incident, meta, onRevert }) {
  const [comparing, setComparing] = useState(null);
  const [confirming, setConfirming] = useState(null);
  const [busy, setBusy] = useState(false);
  const versions = [...incident.history, incident].reverse();

  async function revert(version) {
    if (confirming !== version) return setConfirming(version);
    setBusy(true);
    try {
      await onRevert(version);
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  return (
    <div className="versions">
      <p className="muted">Nothing is ever overwritten. Going back to an old version copies it in as the newest one.</p>
      {versions.map((v) => {
        const isCurrent = v.version === incident.version;
        return (
          <div className={`version ${isCurrent ? "current" : ""}`} key={v.version}>
            <div className="version-head">
              <b>Version {v.version}</b>
              {isCurrent && <span className="tag">current</span>}
              {v.reverted_from && <span className="tag">copied from v{v.reverted_from}</span>}
              <SeverityPill incident={v} />
              <OutcomePill outcome={v.outcome} names={meta.outcome_names} />
            </div>
            <p>{v.description}</p>
            <small className="muted">
              {v.location} · {v.reporter_role} · {v.injury ? "injury" : "no injury"} · saved as of {formatDate(v.timestamp)}
              {v.has_photo && <> · <a href={api.photoUrl(incident.id, isCurrent ? null : v.version)} target="_blank" rel="noreferrer">photo</a></>}
            </small>
            {!isCurrent && (
              <div className="btn-row">
                <button className="btn small" onClick={() => setComparing(comparing === v.version ? null : v.version)}>
                  {comparing === v.version ? "Hide comparison" : "Compare with current"}
                </button>
                <button className="btn small" onClick={() => revert(v.version)} disabled={busy}>
                  <RotateCcw size={13} /> {confirming === v.version ? "Click again to revert" : "Revert to this"}
                </button>
              </div>
            )}
            {comparing === v.version && <VersionCompare previous={v} current={incident} meta={meta} />}
          </div>
        );
      })}
    </div>
  );
}
