// Sufi

// Old and new value side by side: the AI insight always, and the typed answers that changed.
import { OUTCOME_COLORS, SEVERITY_COLORS } from "../labels.js";

function severityText(incident, meta) {
  if (incident.assessment_error) return "Not assessed";
  const level = meta.severity_levels[String(incident.severity_estimate)];
  return `${incident.severity_estimate}/5 ${level ? level.name : ""}`.trim();
}

export default function VersionCompare({ previous, current, meta }) {
  const insight = [
    ["Severity", severityText(previous, meta), severityText(current, meta), SEVERITY_COLORS[current.severity_estimate || 0]],
    ["Action", meta.outcome_names[previous.outcome] || previous.outcome, meta.outcome_names[current.outcome] || current.outcome, OUTCOME_COLORS[current.outcome]],
    ["Hazard type", meta.hazard_names[previous.hazard_type] || previous.hazard_type, meta.hazard_names[current.hazard_type] || current.hazard_type],
  ];
  const typed = [
    ["What happened", previous.description, current.description],
    ["Location", previous.location, current.location],
    ["Reported by", previous.reporter_role, current.reporter_role],
    ["Anyone injured", previous.injury ? "Yes" : "No", current.injury ? "Yes" : "No"],
    ["Photo", previous.photo_file || "none", current.photo_file || "none"],
  ].filter(([, before, after]) => before !== after);

  return (
    <div className="compare">
      {[...typed, ...insight].map(([label, before, after, color]) => (
        <div className="compare-row" key={label}>
          <span className="compare-label">{label}</span>
          {before === after ? (
            <span className="same">{after} (unchanged)</span>
          ) : (
            <span><s className="old">{before}</s> <b>→</b> <b style={{ color }}>{after}</b></span>
          )}
        </div>
      ))}
    </div>
  );
}
