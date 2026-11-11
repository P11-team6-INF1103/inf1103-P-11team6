// Darrel
// One page for the work at hand: log a new incident (the web version of terminal menu option 1: photo picker,
// undo/redo and a review step, see IncidentForm), read the AI report, and triage the open incidents below it.
import { useState } from "react";
import { api } from "../api.js";
import IncidentForm from "../components/IncidentForm.jsx";
import IncidentReport from "../components/IncidentReport.jsx";
import TriageQueue from "../components/TriageQueue.jsx";

export default function LogTriage({ incidents, meta, onOpen, onCreated }) {
  const [result, setResult] = useState(null);

  async function create(data) {
    const created = await api.createIncident(data);
    setResult(created);
    onCreated(created);
  }

  return (
    <>
      <section className="grid-main">
        <IncidentForm mode="new" onSubmit={create} />
        <div className="card">
          {result ? (
            <IncidentReport incident={result} meta={meta} />
          ) : (
            <div className="empty">The AI report for your incident will appear here.</div>
          )}
        </div>
      </section>
      <TriageQueue incidents={incidents} meta={meta} onOpen={onOpen} onChanged={onCreated} />
    </>
  );
}
