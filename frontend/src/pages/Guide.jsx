// Darrel
import { SEVERITY_COLORS } from "../labels.js";

// What each severity level and outcome means (same text as the terminal app).
export default function Guide({ meta }) {
  return (
    <section className="grid-main">
      <div className="card">
        <div className="card-title"><h3>Severity levels</h3></div>
        {Object.entries(meta.severity_levels).map(([level, { name, meaning }]) => (
          <div key={level} className="list-row">
            <div className="list-icon" style={{ color: SEVERITY_COLORS[level] }}>{level}</div>
            <div className="name">{name}<small>{meaning}</small></div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-title"><h3>Outcomes</h3></div>
        {Object.entries(meta.outcome_actions).map(([id, action]) => (
          <div key={id} className="list-row">
            <div className="name">{meta.outcome_names[id]}<small>{action}</small></div>
          </div>
        ))}
      </div>
    </section>
  );
}
