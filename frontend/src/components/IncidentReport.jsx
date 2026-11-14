// Darrel
import { api } from "../api.js";
import { SEVERITY_COLORS, formatDate } from "../labels.js";
import { OutcomePill } from "./Pills.jsx";

function Section({ title, children }) {
  return (
    <div className="report-section">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function BulletList({ items }) {
  return <ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>;
}

// The full report for one incident: the web version of ReportPrinter.print_incident in io_manager.py.
export default function IncidentReport({ incident, meta }) {
  const severity = incident.severity_estimate || 0;
  const level = meta.severity_levels[String(severity)];
  const color = SEVERITY_COLORS[severity];

  return (
    <div className="report">
      <h2>Incident #{incident.id} · {incident.location}</h2>
      <div className="meta">
        {formatDate(incident.timestamp)} · reported by {incident.reporter_role}
        {incident.version > 1 && ` · version ${incident.version}${incident.reverted_from ? ` (copied from version ${incident.reverted_from})` : incident.reanalysed ? " (re-analysed)" : " (edited)"}`}
      </div>

      <dl className="kv">
        <dt>What happened</dt><dd>{incident.description}</dd>
        <dt>Anyone injured</dt><dd>{incident.injury ? "Yes" : "No"}</dd>
        <dt>Type of hazard</dt><dd>{meta.hazard_names[incident.hazard_type] || incident.hazard_type}</dd>
      </dl>

      <Section title="SEVERITY AND ACTION">
        {incident.assessment_error ? (
          <p>Not assessed - the AI could not analyse this incident.</p>
        ) : (
          <>
            <div style={{ fontSize: 22, color }}>{severity}/5 {level ? level.name : ""}</div>
            <div className="gauge">
              {[1, 2, 3, 4, 5].map((n) => <span key={n} style={{ background: n <= severity ? color : undefined }} />)}
            </div>
            {level && <p style={{ marginBottom: 10 }}>{level.meaning}</p>}
            {incident.severity_reasons?.length > 0 && <BulletList items={incident.severity_reasons} />}
          </>
        )}
        <div style={{ marginTop: 12 }}>
          <OutcomePill outcome={incident.outcome} names={meta.outcome_names} />
          <p style={{ marginTop: 8 }}>{meta.outcome_actions[incident.outcome]}</p>
        </div>
      </Section>

      {incident.photo_file && (
        <Section title="WHAT THE PHOTO SHOWS">
          {incident.has_photo && <img src={api.photoUrl(incident.id)} alt="Uploaded scene" />}
          {incident.photo_analysed ? (
            <>
              <p>{incident.photo_summary}</p>
              {incident.photo_matches_description === false && (
                <p className="warn-box">The photo does not seem to match the description.</p>
              )}
              {incident.photo_hazards_seen?.length > 0 && <BulletList items={incident.photo_hazards_seen} />}
              {incident.photo_evidence_used?.length > 0 && (
                <p style={{ marginTop: 8 }}>Used in the score: {incident.photo_evidence_used.join("; ")}</p>
              )}
            </>
          ) : (
            <p>The photo ({incident.photo_file}) could not be analysed.</p>
          )}
        </Section>
      )}

      {incident.weather_available && (
        <Section title="WEATHER AT THE TIME">
          <p>{incident.condition}, {incident.temperature_c}°C, {incident.humidity_pct}% humidity</p>
        </Section>
      )}

      {incident.web_industry_context && (
        <Section title="IS THIS A KNOWN ISSUE IN THE INDUSTRY?">
          <p>{incident.web_industry_context}</p>
        </Section>
      )}

      {incident.web_incidents?.length > 0 && (
        <Section title="SIMILAR INCIDENTS REPORTED ELSEWHERE">
          <ul>
            {incident.web_incidents.map((item, i) => (
              <li key={i}>
                {item.summary} ({item.location}, {item.date}).{" "}
                <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Source</a>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {incident.similar_incidents?.length > 0 && (
        <Section title="SIMILAR INCIDENTS ON OUR OWN SITES">
          <BulletList items={incident.similar_incidents.map((s) => `"${s.description}" - ${s.location} (${meta.outcome_names[s.outcome] || s.outcome})`)} />
        </Section>
      )}

      {incident.review_likely_causes && (
        <Section title="WHY IT LIKELY HAPPENED"><BulletList items={incident.review_likely_causes} /></Section>
      )}
      {incident.review_prevention_actions && (
        <Section title="HOW TO PREVENT IT"><BulletList items={incident.review_prevention_actions} /></Section>
      )}

      {incident.problems?.length > 0 && (
        <Section title="NOTE: SOME AI STEPS DID NOT WORK"><BulletList items={incident.problems} /></Section>
      )}
    </div>
  );
}
