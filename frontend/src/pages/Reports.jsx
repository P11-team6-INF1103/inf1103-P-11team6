// Ren Xiang
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
// Trend and summary report: this period against the one before, the busiest places and hazards, and a trend chart.
import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";

const tooltipStyle = { background: "#131918", border: "1px solid #232c2b", borderRadius: 10, color: "#e9efed" };
const RANGES = [[7, "7 days"], [14, "14 days"], [30, "30 days"], [90, "90 days"]];

// "+2" / "-1" / "no change" for a number against the period before.
function delta(now, before) {
  if (before == null || now == null) return "no earlier period to compare";
  const d = +(now - before).toFixed(1);
  return d === 0 ? "no change" : `${d > 0 ? "+" : ""}${d} vs the period before`;
}

function Figure({ label, value, note, bad }) {
  return (
    <div className="card stat">
      <div className="stat-top">{label}</div>
      <div className="stat-value">{value ?? "-"}</div>
      <div className={`trend ${bad ? "bad" : ""}`}>{note}</div>
    </div>
  );
}

function Ranking({ title, rows, empty }) {
  return (
    <div className="card">
      <div className="card-title"><h3>{title}</h3></div>
      {rows.length === 0 && <div className="empty">{empty}</div>}
      {rows.map((r) => (
        <div key={r.name} className="list-row">
          <div className={`list-icon site-sev sev${r.worst_severity || 1}`}>{r.worst_severity || "-"}</div>
          <div className="name">{r.name}
            <small>{r.share}% of incidents · {r.previous_count} in the period before · worst severity {r.worst_severity || "-"}</small>
          </div>
          <b>{r.count}</b>
        </div>
      ))}
    </div>
  );
}

export default function Reports() {
  const [days, setDays] = useState(7);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let current = true;
    setReport(null);
    api.summary(days)
      .then((body) => { if (current) { setReport(body); setError(null); } })
      .catch((err) => { if (current) setError(err.message); });
    return () => { current = false; };
  }, [days]);

  const overview = report?.sections.overview;
  const chart = report?.sections.trend.map((b) => ({ ...b, label: b.from === b.to ? b.from.slice(5) : `${b.from.slice(5)}…` }));

  return (
    <>
      <div className="card">
        <div className="card-title">
          <h3>Summary for the last {days} days</h3>
          <div className="toggle">
            {RANGES.map(([n, label]) => (
              <button key={n} className={`btn small ${days === n ? "selected" : ""}`} onClick={() => setDays(n)}>{label}</button>
            ))}
            <a className="btn small" href={api.summaryCsvUrl(days)} title="Download as a spreadsheet"><Download size={13} /> CSV</a>
          </div>
        </div>
        {error && <div className="alert error">{error}</div>}
        {!report && !error && <div className="empty">Building the report...</div>}
        {report && (
          <>
            <p className="muted">{report.from} to {report.to}, compared with the {days} days before.</p>
            <ul className="report-notes">{report.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            {report.skipped > 0 && <div className="alert info">{report.skipped} incident(s) with an unreadable date were left out.</div>}
          </>
        )}
      </div>

      {overview && (
        <div className="stats compact">
          <Figure label="Incidents" value={overview.total} note={delta(overview.total, overview.previous_total)} bad={overview.change > 0} />
          <Figure label={`Severe (4+)`} value={overview.severe} note={delta(overview.severe, overview.previous_severe)} bad={overview.severe > overview.previous_severe} />
          <Figure label="Average severity" value={overview.average_severity} note={delta(overview.average_severity, overview.previous_average_severity)} />
          <Figure label="Still open" value={overview.open} note={`${overview.resolved} resolved · ${overview.injuries} with injuries`} />
        </div>
      )}

      {report && (
        <>
          <div className="card">
            <div className="card-title"><h3>Trend</h3><span>{days > 14 ? "One point per week" : "One point per day"}</span></div>
            <div style={{ width: "100%", height: 280 }}>
              <ResponsiveContainer>
                <ComposedChart data={chart}>
                  <CartesianGrid stroke="#232c2b" vertical={false} />
                  <XAxis dataKey="label" stroke="#7d8a87" fontSize={11} interval="preserveStartEnd" />
                  <YAxis yAxisId="count" allowDecimals={false} stroke="#7d8a87" fontSize={11} />
                  <YAxis yAxisId="sev" orientation="right" domain={[0, 5]} stroke="#facc15" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Bar yAxisId="count" dataKey="incidents" name="Incidents" fill="#2fd59b" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar yAxisId="count" dataKey="severe" name="Severe (4+)" fill="#f87171" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Line yAxisId="sev" dataKey="average_severity" name="Average severity" stroke="#facc15" strokeWidth={2} dot connectNulls isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid-main">
            <Ranking title="Busiest locations" rows={report.sections.locations} empty="No incidents in this period." />
            <Ranking title="Most common hazards" rows={report.sections.hazards} empty="No incidents in this period." />
          </div>
        </>
      )}
    </>
  );
}
