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
