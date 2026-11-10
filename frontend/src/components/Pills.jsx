// Darrel
import { OUTCOME_COLORS, PRIORITY_COLORS, SEVERITY_COLORS } from "../labels.js";

export function SeverityPill({ incident }) {
  const severity = incident.assessment_error ? 0 : incident.severity_estimate || 0;
  const color = SEVERITY_COLORS[severity];
  return (
    <span className="pill sev" style={{ color, borderColor: color + "55", background: color + "14" }}>
      {severity || "-"}
    </span>
  );
}

export function OutcomePill({ outcome, names }) {
  const color = OUTCOME_COLORS[outcome] || "#7d8a87";
  return (
    <span className="pill" style={{ color, borderColor: color + "55", background: color + "14" }}>
      {names[outcome] || outcome}
    </span>
  );
}

export function PriorityPill({ incident }) {
  const color = PRIORITY_COLORS[incident.priority] || "#7d8a87";
  return (
    <span className="pill" style={{ color, borderColor: color + "55", background: color + "14" }}
          title={incident.priority_source === "manual" ? "Set by hand" : "Suggested from the severity"}>
      P{incident.priority} {incident.priority_name}
    </span>
  );
}

export function StatusPill({ incident }) {
  const color = incident.resolved ? "#2fd59b" : "#facc15";
  return (
    <span className="pill" style={{ color, borderColor: color + "55", background: color + "14" }}>
      {incident.resolved ? "Resolved" : "Open"}
    </span>
  );
}
