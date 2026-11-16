// Lennart
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { Suspense, lazy, useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { api } from "./api.js";
import { DEFAULT_META } from "./labels.js";
import Sidebar from "./components/Sidebar.jsx";
import SupervisorLogin from "./components/SupervisorLogin.jsx";
import Header from "./components/Header.jsx";
import IncidentDrawer from "./components/IncidentDrawer.jsx";
import Overview from "./pages/Overview.jsx";
import LogTriage from "./pages/LogTriage.jsx";
import Incidents from "./pages/Incidents.jsx";
import Guide from "./pages/Guide.jsx";
import Reports from "./pages/Reports.jsx";
import Profile from "./pages/Profile.jsx";

// The site page is only downloaded when someone opens it.
const SiteModel = lazy(() => import("./pages/SiteModel.jsx"));

const TITLES = {
  overview: ["Welcome back", "Here's what's happening on your sites today"],
  log: ["Log and Incident", "Log what happened, then work through the open incidents, most urgent first"],
  reports: ["Summary report", "How this period compares with the last: trends, busiest places and hazards"],
  incidents: ["Incidents", "Every incident the AI and the rules have assessed"],
  site: ["Site map & locations", "Your site as a 2D pin board, and every place that keeps having incidents"],
  guide: ["Severity guide", "How incidents are scored and routed"],
  profile: ["Profile", "The account you are logged in with"],
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
  // Darrel
  // The logged-in account: undefined while a saved login is being checked, null to show the login page.
  const [user, setUser] = useState(api.hasLogin() ? undefined : null);
  const [loginNotice, setLoginNotice] = useState(null);

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

  // Darrel
  // Checks the saved login on start and whenever someone logs in or out, or the server says the login ran out.
  useEffect(() => {
    function check() {
      if (!api.hasLogin()) {
        setUser(null);
        return;
      }
      api.session().then((s) => setUser(s.username)).catch((err) => {
        setLoginNotice(err.message);
        setUser(null);
      });
    }
    check();
    window.addEventListener("supervisor-change", check);
    return () => window.removeEventListener("supervisor-change", check);
  }, []);

  useEffect(() => {
    if (!user) return; // every route needs a login, so load nothing until there is one
    api.meta().then(setMeta).catch(() => {});
    loadIncidents();
  }, [user]);

  // Darrel
  function handleLogout() {
    setLoginNotice(null);
    setPage("overview");
    setSelected(null);
    api.logout();
  }

  function handleSearch(text) {
    setSearch(text);
    if (text && page !== "incidents" && page !== "overview") setPage("overview");
  }

  async function handleDelete(incident) {
    try {
      await api.deleteIncident(incident.id);
      setSelected(null);
      setIncidents((current) => current.filter((i) => i.id !== incident.id)); // drop the row now; the reload below renumbers
      await loadIncidents();
    } catch (err) {
      setLoadError(err.message);
    }
  }

  // Darrel
  if (user === undefined) return <div className="login-page"><div className="empty">Checking your login...</div></div>;
  if (!user) {
    return <SupervisorLogin notice={loginNotice} onLogin={(name) => { setLoginNotice(null); setUser(name); }} />;
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
               user={user} onLogout={handleLogout}
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
        {page === "profile" && <Profile />}
      </main>
      {selected && (
        <IncidentDrawer key={selected.incident.id + selected.mode} incident={selected.incident} initialMode={selected.mode}
                        meta={meta}
                        onClose={() => setSelected(null)} onDelete={handleDelete} onChanged={loadIncidents} />
      )}
    </div>
  );
}
