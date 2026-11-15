// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { useState } from "react";
import { Download } from "lucide-react";
import { api } from "../api.js";
import IncidentTable from "../components/IncidentTable.jsx";
import { needsReview } from "../labels.js";

// Web version of the terminal summary: every incident, filterable, manual reviews and most severe first.
export default function Incidents({ incidents, meta, search, onOpen, onEdit }) {
  const [outcome, setOutcome] = useState("");
  const [hazard, setHazard] = useState("");
  const [photoOnly, setPhotoOnly] = useState(false);

  const text = search.trim().toLowerCase();
  const shown = incidents
    .filter((i) => !outcome || i.outcome === outcome)
    .filter((i) => !hazard || i.hazard_type === hazard)
    .filter((i) => !photoOnly || i.photo_file)
    .filter((i) => !text || `${i.description} ${i.location} ${i.reporter_role}`.toLowerCase().includes(text))
    .sort((a, b) => (needsReview(b) - needsReview(a)) || ((b.severity_estimate || 0) - (a.severity_estimate || 0)));

  const hazardTypes = [...new Set(incidents.map((i) => i.hazard_type).filter(Boolean))];

  return (
    <div className="card">
      <div className="card-title">
        <h3>All incidents</h3>
        <span>{shown.length} of {incidents.length} shown · manual reviews first, then most severe</span>
      </div>
      <div className="toolbar">
        <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
          <option value="">All actions</option>
          {Object.entries(meta.outcome_names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select className="input" value={hazard} onChange={(e) => setHazard(e.target.value)}>
          <option value="">All hazards</option>
          {hazardTypes.map((h) => <option key={h} value={h}>{meta.hazard_names[h] || h}</option>)}
        </select>
        <button className={`btn ${photoOnly ? "selected" : ""}`} onClick={() => setPhotoOnly(!photoOnly)}>
          With photo only
        </button>
        <a className="btn" href={api.exportUrl("csv")} title="Download every incident as a spreadsheet file"><Download size={14} /> Export CSV</a>
      </div>
      <IncidentTable incidents={shown} meta={meta} onOpen={onOpen} onEdit={onEdit} />
    </div>
  );
}
