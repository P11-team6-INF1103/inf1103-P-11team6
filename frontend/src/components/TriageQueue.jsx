// Darrel
// The open incidents ordered by priority, then severity, then age, with quick resolve. Sits under the log form on the Log & triage page.
import { useState } from "react";
import { AlertTriangle, CheckCheck, CheckCircle2, ClipboardList } from "lucide-react";
import { api } from "../api.js";
import IncidentTable from "./IncidentTable.jsx";

// One small number card above the queue.
function Count({ label, value, icon: Icon }) {
  return (
    <div className="card stat">
      <div className="stat-top">{label}<span className="stat-icon"><Icon size={15} /></span></div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
