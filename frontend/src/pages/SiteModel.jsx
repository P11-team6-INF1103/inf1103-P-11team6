// Darrel
import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { placeIncidents, severityOf } from "../site/placement.js";
import { drawablePlan } from "../site/kinds.js";
import SiteUpload from "../components/SiteUpload.jsx";
import SiteReview from "../components/SiteReview.jsx";
import SiteMap from "../components/SiteMap.jsx";
import LocationsPanel from "../components/LocationsPanel.jsx";

const DAY_MS = 24 * 3600 * 1000;

// The 2D site map page: upload a plan, review what was read, then watch incidents pinned on the map.
// The locations (query by place, saved places) sit under the map, so places and the plan are on one page.
export default function SiteModel({ incidents, meta, onOpen, onEdit }) {
  const [plan, setPlan] = useState(undefined);       // undefined while loading, null if none is saved
  const [loadError, setLoadError] = useState(null);
  const [draft, setDraft] = useState(null);          // { plan, warnings, source } while the user is reviewing
  const [notice, setNotice] = useState(null);

  const [minSeverity, setMinSeverity] = useState(3);
  const [days, setDays] = useState(30);
  const [heatOn, setHeatOn] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [focus, setFocus] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    api.sitePlan().then((r) => setPlan(r.plan)).catch((err) => { setLoadError(err.message); setPlan(null); });
  }, []);

  const drawn = useMemo(() => (plan ? drawablePlan(plan) : null), [plan]);

  const { pins, heat, unplaced, byElement } = useMemo(() => {
    if (!drawn) return { pins: [], heat: {}, unplaced: [], byElement: [] };
    const since = days >= 999 ? 0 : Date.now() - days * DAY_MS;
    const recent = incidents.filter((i) => severityOf(i) >= minSeverity && (since === 0 || !(new Date(i.timestamp).getTime() < since)));
    const { placed, unplaced: loose } = placeIncidents(drawn, recent);
    const counts = {};
    const lists = {};
    placed.forEach(({ element, incident }) => {
      counts[element.id] = (counts[element.id] || 0) + 1;
      (lists[element.id] ||= { element, incidents: [] }).incidents.push(incident);
    });
    return {
      heat: counts, unplaced: loose,
      pins: placed.map(({ incident, element, spot }) => ({
        id: incident.id, sev: severityOf(incident), x: spot.x, y: spot.y,
        label: `#${incident.id} · Sev ${severityOf(incident)} · ${incident.location}`, elementId: element.id,
      })),
      byElement: Object.values(lists).sort((a, b) => b.incidents.length - a.incidents.length),
    };
  }, [drawn, incidents, minSeverity, days]);

  function startReview(newPlan, warnings, source) {
    setNotice(null);
    setDraft({ plan: newPlan, warnings, source });
  }

  function saved(newPlan, fixed) {
    setPlan(newPlan);
    setDraft(null);
    setNotice(fixed.length ? fixed.join(" ") : null);
    setFocus(null);
  }

  async function removePlan() {
    try {
      await api.deleteSitePlan();
      setPlan(null); setConfirmDelete(false); setSelectedId(null);
    } catch (err) {
      setNotice(err.message);
    }
  }

  function openPin(id) {
    const incident = incidents.find((i) => i.id === id);
    if (!incident) return;
    setSelectedId(id);
    const pin = pins.find((p) => p.id === id);
    if (pin) setFocus({ x: pin.x, y: pin.y });
    onOpen(incident);
  }

  if (plan === undefined) return <div className="empty">Loading the site map...</div>;
  if (draft) {
    return <SiteReview draft={draft.plan} warnings={draft.warnings} source={draft.source}
                       onSaved={saved} onCancel={() => setDraft(null)} />;
  }
  if (!plan) {
    return (
      <>
        {loadError && <div className="alert error">{loadError}</div>}
        <SiteUpload onDraft={startReview} />
        <LocationsPanel incidents={incidents} meta={meta} onOpen={onOpen} onEdit={onEdit} />
      </>
    );
  }

  const total = pins.length;
  return (
    <>
      <div className="grid-main">
      <div className="column">
        <div className="card">
          <div className="card-title">
            <h3>{plan.name}</h3>
            <span>{plan.width_m} m × {plan.depth_m} m · {plan.elements.length} areas</span>
          </div>
          <div className="toolbar site-controls">
            <div className="toggle" role="group" aria-label="Minimum severity">
              {[[1, "All"], [2, "2+"], [3, "3+"], [4, "4+"], [5, "5"]].map(([s, label]) => <button key={s} className={`btn ${minSeverity === s ? "selected" : ""}`} onClick={() => setMinSeverity(s)}>{label}</button>)}
            </div>
            <div className="toggle" role="group" aria-label="Period">
              {[[7, "7 days"], [30, "30 days"], [999, "All"]].map(([d, label]) => <button key={d} className={`btn ${days === d ? "selected" : ""}`} onClick={() => setDays(d)}>{label}</button>)}
            </div>
            <label className="site-check"><input type="checkbox" checked={heatOn} onChange={(e) => setHeatOn(e.target.checked)} /> Heat</label>
          </div>
          <SiteMap plan={drawn} pins={pins} heat={heat} heatOn={heatOn}
                   selectedId={selectedId} focus={focus} onPick={openPin} />
          <div className="site-legend">
            {[1, 2, 3, 4, 5].filter((s) => s >= minSeverity).map((s) => <span key={s}><i className={`site-dot sev${s}`} /> Severity {s}{s === 5 ? " (pulses)" : ""}</span>)}
            <span>Each pin is one incident; the glow marks the hotspots</span>
          </div>
          {notice && <div className="alert info" style={{ marginTop: 12 }}>{notice}</div>}
        </div>
      </div>

      <div className="column">
        <div className="card">
          <div className="card-title"><h3>Hotspots</h3><span>{total} pinned</span></div>
          {byElement.length === 0 && <div className="empty">No incidents at severity {minSeverity === 1 ? "any level" : `${minSeverity}+`} match this plan yet.</div>}
          {byElement.map(({ element, incidents: list }) => {
            const worst = Math.max(...list.map(severityOf));
            return (
              <div key={element.id} className="list-row" style={{ cursor: "pointer" }}
                   onClick={() => setFocus({ x: element.x + element.w / 2, y: element.y + element.d / 2 })}>
                <div className={`list-icon site-sev sev${worst}`}>{worst}</div>
                <div className="name">{element.name}<small>{list.length} incident{list.length === 1 ? "" : "s"} · worst severity {worst}</small></div>
                <b>{list.length}</b>
              </div>
            );
          })}
        </div>

        {unplaced.length > 0 && (
          <div className="card">
            <div className="card-title"><h3>Not on the plan</h3><span>{unplaced.length}</span></div>
            <p className="site-note">These locations match no element. Add the location text as an "other name" on the right element.</p>
            {[...new Set(unplaced.map((i) => i.location))].map((loc) => <div key={loc} className="site-loc">{loc}</div>)}
          </div>
        )}

        <div className="card">
          <div className="card-title"><h3>Site plan</h3></div>
          <div className="site-downloads">
            <button className="btn" onClick={() => setDraft({ plan, warnings: [], source: "edit" })}>Edit the plan</button>
            <button className="btn" onClick={() => { setPlan(null); }}>Upload a new plan</button>
            {!confirmDelete
              ? <button className="btn danger" onClick={() => setConfirmDelete(true)}>Delete plan</button>
              : <><button className="btn danger" onClick={removePlan}>Yes, delete it</button><button className="btn" onClick={() => setConfirmDelete(false)}>Keep</button></>}
          </div>
          <p className="site-note">The plan you confirm is saved on the server, so everyone sees the same map.</p>
        </div>
      </div>
      </div>
      <LocationsPanel incidents={incidents} meta={meta} onOpen={onOpen} onEdit={onEdit} />
    </>
  );
}
