// Lennart
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { Suspense, lazy, useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { api } from "./api.js";
import { DEFAULT_META } from "./labels.js";
import Sidebar from "./components/Sidebar.jsx";
import Header from "./components/Header.jsx";
import IncidentDrawer from "./components/IncidentDrawer.jsx";
import Overview from "./pages/Overview.jsx";
import LogTriage from "./pages/LogTriage.jsx";
import Incidents from "./pages/Incidents.jsx";
import Guide from "./pages/Guide.jsx";
import Reports from "./pages/Reports.jsx";

// The site page is only downloaded when someone opens it.
const SiteModel = lazy(() => import("./pages/SiteModel.jsx"));

const TITLES = {
  overview: ["Welcome back", "Here's what's happening on your sites today"],
  log: ["Log & triage", "Log what happened, then work through the open incidents, most urgent first"],
  reports: ["Summary report", "How this period compares with the last: trends, busiest places and hazards"],
  incidents: ["Incidents", "Every incident the AI and the rules have assessed"],
  site: ["Site map & locations", "Your site as a 2D pin board, and every place that keeps having incidents"],
  guide: ["Severity guide", "How incidents are scored and routed"],
};

export default function App() {
  const [page, setPage] = useState("overview");
  const [incidents, setIncidents] = useState([]);
  const [meta, setMeta] = useState(DEFAULT_META);
  const [serverStatus, setServerStatus] = useState("connecting");
  const [loadError, setLoadError] = useState(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null); // { incident, mode } for the drawer
  const [menuOpen, setMenuOpen] = useState(false); // the phone menu

  async function loadIncidents() {
    try {
      setIncidents(await api.incidents());
      setServerStatus("ok");
      setLoadError(null);
    } catch (err) {
      setServerStatus("down");
      setLoadError(err.message);
    }
  }

  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
    loadIncidents();
  }, []);

  function handleSearch(text) {
    setSearch(text);
    if (text && page !== "incidents" && page !== "overview") setPage("overview");
  }

  async function handleDelete(incident) {
    try {
      await api.deleteIncident(incident.id);
      setSelected(null);
      await loadIncidents();
    } catch (err) {
      setLoadError(err.message);
    }
  }

  const [title, subtitle] = TITLES[page];
  const shared = {
    incidents, meta,
    onOpen: (incident) => setSelected({ incident, mode: "report" }),
    onEdit: (incident) => setSelected({ incident, mode: "edit" }),
    onDelete: handleDelete,
  };

  return (
    <div className="layout">
      <div className="topbar">
        <button className="icon-btn" aria-label="Open menu" onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
        <div className="brand-logo"><span /></div>
        <strong>Workplace</strong>
      </div>
      <Sidebar page={page} onNavigate={(id) => { setPage(id); setMenuOpen(false); window.scrollTo(0, 0); }} serverStatus={serverStatus}
               open={menuOpen} onClose={() => setMenuOpen(false)} />
      {menuOpen && <div className="nav-backdrop" onClick={() => setMenuOpen(false)} />}
      <main className="main">
        <Header title={title} subtitle={subtitle} search={search} onSearch={handleSearch} />
        {loadError && (
          <div className="alert error">
            {loadError} <button className="btn" style={{ marginLeft: 10 }} onClick={loadIncidents}>Retry</button>
          </div>
        )}
        {page === "overview" && <Overview {...shared} search={search} />}
        {page === "log" && <LogTriage {...shared} onCreated={loadIncidents} />}
        {page === "incidents" && <Incidents {...shared} search={search} />}
        {page === "reports" && <Reports />}
        {page === "site" && <Suspense fallback={<div className="empty">Loading the site map...</div>}><SiteModel {...shared} /></Suspense>}
        {page === "guide" && <Guide meta={meta} />}
      </main>
      {selected && (
        <IncidentDrawer key={selected.incident.id + selected.mode} incident={selected.incident} initialMode={selected.mode}
                        meta={meta}
                        onClose={() => setSelected(null)} onDelete={handleDelete} onChanged={loadIncidents} />
      )}
    </div>
  );
}
