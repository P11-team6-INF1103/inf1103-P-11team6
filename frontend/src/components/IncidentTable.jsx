// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { Camera, Pencil } from "lucide-react";
import { formatDate } from "../labels.js";
import { OutcomePill, PriorityPill, SeverityPill, StatusPill } from "./Pills.jsx";

// onAction(incident) may return a button for an extra last column.
export default function IncidentTable({ incidents, meta, onOpen, onEdit, onAction }) {
  if (incidents.length === 0) {
    return <div className="empty">No incidents to show.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="incident-table">
        <thead>
          <tr>
            <th>#</th><th>When</th><th>Location</th><th>Hazard</th><th>Sev</th><th>Priority</th><th>Status</th><th>Action</th><th>What happened</th>{onEdit && <th></th>}{onAction && <th></th>}
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <tr key={incident.id} onClick={() => onOpen(incident)}>
              <td className="c-id">#{incident.id}</td>
              <td className="c-when">{formatDate(incident.timestamp)}</td>
              <td className="c-loc">{incident.location}</td>
              <td className="c-haz">{meta.hazard_names[incident.hazard_type] || incident.hazard_type}</td>
              <td className="c-sev"><SeverityPill incident={incident} /></td>
              <td className="c-pri"><PriorityPill incident={incident} /></td>
              <td className="c-stat"><StatusPill incident={incident} /></td>
              <td className="c-act"><OutcomePill outcome={incident.outcome} names={meta.outcome_names} /></td>
              <td className="wrap c-desc">
                {incident.photo_file && <Camera size={13} style={{ marginRight: 6, verticalAlign: -2 }} />}
                {incident.description}
                {incident.version > 1 && <span className="tag">v{incident.version}</span>}
              </td>
              {onAction && <td className="c-btn">{onAction(incident)}</td>}
              {onEdit && (
                <td className="c-btn">
                  <button className="btn small" onClick={(e) => { e.stopPropagation(); onEdit(incident); }}>
                    <Pencil size={13} /> Edit
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
