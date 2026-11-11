// Darrel
import { LayoutDashboard, ClipboardPlus, List, Map, BookOpen, FileBarChart, X } from "lucide-react";

const NAVIGATION = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "log", label: "Log & triage", icon: ClipboardPlus },
  { id: "incidents", label: "Incidents", icon: List },
  { id: "reports", label: "Summary report", icon: FileBarChart },
  { id: "site", label: "Site map", icon: Map },
];

// open and onClose only matter on phones, where the sidebar slides in over the page.
export default function Sidebar({ page, onNavigate, serverStatus, open, onClose }) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
      <div className="brand">
        <div className="brand-logo"><span /></div>
        <div>
          <div className="brand-name">SiteSafe</div>
          <div className="brand-sub">Incident triage</div>
        </div>
        <button className="icon-btn sidebar-close" aria-label="Close menu" onClick={onClose}><X size={18} /></button>
      </div>

      <div className="nav-label">NAVIGATION</div>
      {NAVIGATION.map(({ id, label, icon: Icon }) => (
        <button key={id} title={label} className={`nav-item ${page === id ? "active" : ""}`} onClick={() => onNavigate(id)}>
          <Icon size={17} /> <span className="nav-text">{label}</span>
        </button>
      ))}

      <div className="nav-label">HELP</div>
      <button title="Severity guide" className={`nav-item ${page === "guide" ? "active" : ""}`} onClick={() => onNavigate("guide")}>
        <BookOpen size={17} /> <span className="nav-text">Severity guide</span>
      </button>

      <div className="nav-spacer" />
      <div className="server-status">
        <span className={`dot ${serverStatus}`} />
        <span className="nav-text">{serverStatus === "ok" ? "Server online" : serverStatus === "down" ? "Server offline" : "Connecting..."}</span>
      </div>
    </aside>
  );
}
