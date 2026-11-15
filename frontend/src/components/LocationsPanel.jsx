// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { useState } from "react";
import { MapPin } from "lucide-react";
import { api } from "../api.js";
import IncidentTable from "./IncidentTable.jsx";

// Web version of terminal menu option 3: incidents at one location in the last N days, and the saved locations.
// Shown under the site map, so places and the plan are on one page.
export default function LocationsPanel({ incidents, meta, onOpen, onEdit }) {
  const [location, setLocation] = useState("");
  const [days, setDays] = useState(30);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const counts = {};
  incidents.forEach((i) => { counts[i.location] = (counts[i.location] || 0) + 1; });
  const locations = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  async function search(name = location) {
    setLocation(name);
    setError(null);
    try {
      setResults(await api.queryLocation(name, days));
    } catch (err) {
      setError(err.message);
      setResults(null);
    }
  }

  return (
    <section className="grid-main">
      <div className="card">
        <div className="card-title">
          <h3>Query by location</h3>
          <span>3 or more incidents in 30 days means systemic escalation</span>
        </div>
        <div className="toolbar">
          <input className="input" placeholder="Site A - Block 3" value={location} onChange={(e) => setLocation(e.target.value)} />
          <input className="input" type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} style={{ minWidth: 90 }} />
          <button className="btn primary" onClick={() => search()}>Search</button>
        </div>
        {error && <div className="alert error">{error}</div>}
        {results && (
          <>
            <p style={{ color: "var(--muted)" }}>{results.length} incident(s) at {location} in the last {days} days</p>
            <IncidentTable incidents={results} meta={meta} onOpen={onOpen} onEdit={onEdit} />
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title"><h3>Saved locations</h3></div>
        {locations.length === 0 && <div className="empty">No incidents saved yet.</div>}
        {locations.map(([name, count]) => (
          <div key={name} className="list-row" style={{ cursor: "pointer" }} onClick={() => search(name)}>
            <div className="list-icon"><MapPin size={15} /></div>
            <div className="name">{name}<small>{count >= 3 ? "Repeated incidents" : "Click to see incidents"}</small></div>
            <b style={{ color: count >= 3 ? "var(--warn)" : undefined }}>{count}</b>
          </div>
        ))}
      </div>
    </section>
  );
}
