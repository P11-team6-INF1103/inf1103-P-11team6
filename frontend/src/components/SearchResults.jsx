// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
// Ranked search over every incident, shown on the Overview when the search bar at the top has text:
// words, "exact phrases" and #numbers, plus filters.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import IncidentTable from "../components/IncidentTable.jsx";

const EMPTY = { severity_min: "", hazard: "", outcome: "", priority: "", status: "", date_from: "", date_to: "", has_photo: false };

export default function SearchResults({ query, meta, onOpen, onEdit }) {
  const [filters, setFilters] = useState(EMPTY);
  const [reply, setReply] = useState(null);
  const [error, setError] = useState(null);
  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  // Search as people type, after a short pause so every key press is not a request.
  useEffect(() => {
    let current = true;
    const timer = setTimeout(() => {
      api.search({ ...filters, q: query })
        .then((body) => { if (current) { setReply(body); setError(null); } })
        .catch((err) => { if (current) setError(err.message); });
    }, 250);
    return () => { current = false; clearTimeout(timer); };
  }, [filters, query]);

  const filtered = Object.values(filters).some(Boolean);
  return (
    <div className="card">
      <div className="card-title">
        <h3>Search results for "{query}"</h3>
        <span>{reply ? `${reply.count} of ${reply.total} found` : "Searching..."}</span>
      </div>
      <div className="toolbar">
        <select className="input" value={filters.severity_min} onChange={set("severity_min")}>
          <option value="">Any severity</option>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Severity {n}+</option>)}
        </select>
        <select className="input" value={filters.hazard} onChange={set("hazard")}>
          <option value="">All hazards</option>
          {Object.entries(meta.hazard_names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select className="input" value={filters.outcome} onChange={set("outcome")}>
          <option value="">All actions</option>
          {Object.entries(meta.outcome_names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select className="input" value={filters.priority} onChange={set("priority")}>
          <option value="">Any priority</option>
          {Object.entries(meta.priority_levels || {}).map(([id, name]) => <option key={id} value={id}>P{id} {name}</option>)}
        </select>
        <select className="input" value={filters.status} onChange={set("status")}>
          <option value="">Open and resolved</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
        <input className="input" type="date" title="From" value={filters.date_from} onChange={set("date_from")} />
        <input className="input" type="date" title="To" value={filters.date_to} onChange={set("date_to")} />
        <label className="check"><input type="checkbox" checked={filters.has_photo} onChange={set("has_photo")} /> With photo</label>
        {filtered && <button className="btn" onClick={() => setFilters(EMPTY)}>Clear</button>}
      </div>
      {error && <div className="alert error">{error}</div>}
      {reply && <IncidentTable incidents={reply.results} meta={meta} onOpen={onOpen} onEdit={onEdit} />}
      {reply && reply.results.length > 0 && (
        <p className="muted small">Best matches first. Each word must appear somewhere in the incident.</p>
      )}
    </div>
  );
}
