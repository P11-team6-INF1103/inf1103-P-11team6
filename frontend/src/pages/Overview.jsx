// Sufi

import { AlertTriangle, ClipboardList, Eye, Gauge, OctagonX, Camera, TrendingUp, CheckCircle2 } from "lucide-react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import StatCard from "../components/StatCard.jsx";
import IncidentTable from "../components/IncidentTable.jsx";
import SearchResults from "../components/SearchResults.jsx";
import HazardDonut from "../components/HazardDonut.jsx"; // Lennart
import { OUTCOME_COLORS, dayKey, needsReview } from "../labels.js";

// The last `count` days as "YYYY-MM-DD" strings, oldest first.
function lastDays(count) {
  const days = [];
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

// Number of matching incidents per day, as [{ day, value }] for the small charts.
function dailyCounts(incidents, days, match = () => true) {
  return days.map((day) => ({
    day,
    value: incidents.filter((i) => dayKey(i.timestamp) === day && match(i)).length,
  }));
}

function lastWeek(series) {
  return series.slice(-7).reduce((sum, point) => sum + point.value, 0);
}

const tooltipStyle = { background: "#131918", border: "1px solid #232c2b", borderRadius: 10, color: "#e9efed" };

// With text in the search bar at the top, the page shows the ranked search results instead of the charts.
export default function Overview({ incidents, meta, search = "", onOpen, onEdit }) {
  const days14 = lastDays(14);
  const days30 = lastDays(30);
  const scored = incidents.filter((i) => !i.assessment_error && i.severity_estimate);
  const averageSeverity = scored.length
    ? (scored.reduce((sum, i) => sum + i.severity_estimate, 0) / scored.length).toFixed(1)
    : "-";

  const totalSeries = dailyCounts(incidents, days14);
  const stopSeries = dailyCounts(incidents, days14, (i) => i.outcome === "stop_work_review");
  const reviewSeries = dailyCounts(incidents, days14, needsReview);
  const photoSeries = dailyCounts(incidents, days14, (i) => i.photo_file);

  // Big chart: incidents per day and the average severity that day.
  const trend = days30.map((day) => {
    const onDay = incidents.filter((i) => dayKey(i.timestamp) === day);
    const sev = onDay.filter((i) => i.severity_estimate);
    return {
      day: day.slice(5),
      incidents: onDay.length,
      severity: sev.length ? +(sev.reduce((s, i) => s + i.severity_estimate, 0) / sev.length).toFixed(1) : null,
    };
  });

  // Donut: incidents by hazard type.
  const hazardCounts = {};
  incidents.forEach((i) => {
    const name = meta.hazard_names[i.hazard_type] || i.hazard_type || "Unknown";
    hazardCounts[name] = (hazardCounts[name] || 0) + 1;
  });
  const hazards = Object.entries(hazardCounts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

  const outcomes = [
    { id: "stop_work_review", icon: OctagonX },
    { id: "systemic_escalation", icon: TrendingUp },
    { id: "photo_review", icon: Camera },
    { id: "pending_review", icon: Eye },
    { id: "log_only", icon: CheckCircle2 },
  ].map((o) => ({ ...o, count: incidents.filter((i) => i.outcome === o.id).length }));

  const recent = [...incidents].sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp))).slice(0, 6);

  if (search.trim()) return <SearchResults query={search.trim()} meta={meta} onOpen={onOpen} onEdit={onEdit} />;

  return (
    <>
      <section className="stats">
        <StatCard label="Total incidents" value={incidents.length} icon={ClipboardList}
                  series={totalSeries} trend={`+${lastWeek(totalSeries)}`} />
        <StatCard label="Stop-work reviews" value={incidents.filter((i) => i.outcome === "stop_work_review").length}
                  icon={AlertTriangle} series={stopSeries} trend={`+${lastWeek(stopSeries)}`} trendBad />
        <StatCard label="Needs manual review" value={incidents.filter(needsReview).length}
                  icon={Eye} series={reviewSeries} trend={`+${lastWeek(reviewSeries)}`} trendBad />
        <StatCard label="Average severity" value={averageSeverity} icon={Gauge}
                  series={photoSeries} trend={`${lastWeek(photoSeries)} with photo`} />
      </section>

      <section className="grid-main">
        <div className="column">
          <div className="card">
            <div className="card-title">
              <h3>Incidents vs severity</h3>
              <span>Last 30 days</span>
            </div>
            <div className="big-number">
              {lastWeek(dailyCounts(incidents, days30))}
              <small>incidents in the last 7 days</small>
            </div>
            <div style={{ height: 250 }}>
              <ResponsiveContainer>
                <ComposedChart data={trend} margin={{ top: 10, right: -20, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="fillIncidents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2fd59b" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#2fd59b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#232c2b" vertical={false} />
                  <XAxis dataKey="day" stroke="#4b5654" tickLine={false} axisLine={false} interval={4} fontSize={12} />
                  <YAxis yAxisId="count" stroke="#4b5654" tickLine={false} axisLine={false} allowDecimals={false} fontSize={12} />
                  <YAxis yAxisId="sev" orientation="right" domain={[0, 5]} stroke="#4b5654" tickLine={false} axisLine={false} fontSize={12} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "#7d8a87" }} />
                  <Area yAxisId="count" type="monotone" dataKey="incidents" name="Incidents"
                        stroke="#2fd59b" strokeWidth={2} fill="url(#fillIncidents)" />
                  <Line yAxisId="sev" type="linear" dataKey="severity" name="Avg severity"
                        stroke="#7de8c3" strokeDasharray="4 4" dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <div className="card-title">
              <h3>Recent incidents</h3>
              <span>Click a row for the full report</span>
            </div>
            <IncidentTable incidents={recent} meta={meta} onOpen={onOpen} onEdit={onEdit} />
          </div>
        </div>

        <div className="column">
          <div className="card">
            <div className="card-title"><h3>Incidents by hazard</h3></div>
            <HazardDonut hazards={hazards} total={incidents.length} />
          </div>

          <div className="card">
            <div className="card-title">
              <h3>Outcomes</h3>
              <span>What the rules decided</span>
            </div>
            {outcomes.map(({ id, icon: Icon, count }) => (
              <div key={id} className="list-row">
                <div className="list-icon" style={{ color: OUTCOME_COLORS[id] }}><Icon size={15} /></div>
                <div className="name">
                  {meta.outcome_names[id]}
                  <small>{incidents.length ? Math.round((count / incidents.length) * 100) : 0}% of incidents</small>
                </div>
                <b>{count}</b>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
