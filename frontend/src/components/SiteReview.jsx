// Ren Xiang
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import { useMemo, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { api } from "../api.js";
import { KINDS, drawablePlan, kindOf } from "../site/kinds.js";
import SiteMap from "./SiteMap.jsx";

// Turns what is in the table into what the server expects.
function toPayload(plan) {
  const num = (v) => (v === "" || v === null || v === undefined || !Number.isFinite(Number(v)) ? undefined : Number(v));
  return {
    name: plan.name, width_m: num(plan.width_m), depth_m: num(plan.depth_m),
    elements: plan.elements.map((el) => ({
      type: el.type, name: el.name, x: num(el.x), y: num(el.y), w: num(el.w), d: num(el.d),
      radius_m: el.type === "tower_crane" ? num(el.radius_m) : undefined,
      aliases: Array.isArray(el.aliases) ? el.aliases : String(el.aliases || "").split(",").map((a) => a.trim()).filter(Boolean),
    })),
  };
}

// The "also called" names of one area: location texts that should land on it. Type a name and press Enter or a comma.
function AlsoCalled({ names, onChange }) {
  const [text, setText] = useState("");
  const add = () => {
    const name = text.trim().replace(/,$/, "").trim();
    if (name && !names.includes(name)) onChange([...names, name]);
    setText("");
  };
  return (
    <div className="chips">
      {names.map((n) => (
        <span key={n} className="chip">{n}
          <button type="button" aria-label={`Remove ${n}`} onClick={() => onChange(names.filter((x) => x !== n))}><X size={12} /></button>
        </span>
      ))}
      <input className="input chip-input" placeholder={names.length ? "" : "e.g. Scaffold"} value={text}
             onChange={(e) => setText(e.target.value)} onBlur={add}
             onKeyDown={(e) => {
               if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
               else if (e.key === "Backspace" && !text && names.length) onChange(names.slice(0, -1));
             }} />
    </div>
  );
}

// Step 2: check what the AI (or the template) produced, fix anything wrong, then save. The plan is edited on the map
// itself: click an area to select it, drag it to move it, drag a corner to resize it. No coordinates are typed.
export default function SiteReview({ draft, warnings, source, onSaved, onCancel }) {
  const [plan, setPlan] = useState(() => ({ ...draft, elements: draft.elements.map((el, n) => ({ ...el, id: el.id || `e${n + 1}` })) }));
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const drawn = useMemo(() => drawablePlan(plan), [plan]);
  const selected = plan.elements.find((el) => el.id === selectedId) || null;
  const aliasList = (el) => (Array.isArray(el.aliases) ? el.aliases : String(el.aliases || "").split(",").map((a) => a.trim()).filter(Boolean));
  const change = (id, fields) =>
    setPlan((p) => ({ ...p, elements: p.elements.map((el) => (el.id === id ? { ...el, ...fields } : el)) }));
  const remove = (id) => { setPlan((p) => ({ ...p, elements: p.elements.filter((el) => el.id !== id) })); setSelectedId(null); };
  const add = () => {
    const id = `n${Date.now()}`;
    const w = Math.min(12, drawn.width_m / 2);
    const d = Math.min(10, drawn.depth_m / 2);
    setPlan((p) => ({
      ...p, elements: [...p.elements, { id, type: "zone", name: "New area", x: (drawn.width_m - w) / 2, y: (drawn.depth_m - d) / 2, w, d, aliases: [] }],
    }));
    setSelectedId(id);
  };

  async function save() {
    setError(null);
    setSaving(true);
    try {
      const { plan: saved, warnings: fixed } = await api.saveSitePlan(toPayload(plan));
      onSaved(saved, fixed || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid-main">
      <div className="card">
        <div className="card-title">
          <h3>Check the site plan</h3>
          <span>{source === "ai" ? "The AI read your picture. Fix anything wrong, then save." : "Change anything, then save."}</span>
        </div>
        {warnings.length > 0 && <div className="alert info">{warnings.map((w) => <div key={w}>{w}</div>)}</div>}
        <SiteMap plan={drawn} height={480} editing editId={selectedId} onSelectElement={setSelectedId} onChangeElement={change} />
      </div>

      <div className="column">
        <div className="card">
          <div className="field"><label htmlFor="rv-name">Site name</label>
            <input id="rv-name" className="input" value={plan.name || ""} onChange={(e) => setPlan({ ...plan, name: e.target.value })} /></div>
        </div>

        <div className="card">
          {selected ? (
            <>
              <div className="card-title"><h3>Selected area</h3></div>
              <div className="field"><label htmlFor="rv-area-name">Name</label>
                <input id="rv-area-name" className="input" value={selected.name} onChange={(e) => change(selected.id, { name: e.target.value })} /></div>
              <div className="field"><label htmlFor="rv-area-type">What is it?</label>
                <select id="rv-area-type" className="input" value={kindOf(selected.type).key} onChange={(e) => change(selected.id, { type: e.target.value })}>
                  {KINDS.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}</select></div>
              <div className="field"><label>Also called</label>
                <AlsoCalled key={selected.id} names={aliasList(selected)} onChange={(names) => change(selected.id, { aliases: names })} />
                <small className="muted">Other names people type as the incident location. Incidents with these names are pinned here.</small></div>
              <button className="btn danger" onClick={() => remove(selected.id)}><Trash2 size={14} /> Delete this area</button>
            </>
          ) : (
            <div className="empty">Click an area on the map to rename it, change what it is, or delete it. Drag it to move it and drag a corner to resize it.</div>
          )}
        </div>

        <div className="card">
          <div className="card-title"><h3>Areas on this plan</h3><span>{plan.elements.length}</span></div>
          {plan.elements.length === 0 && <div className="empty">No areas yet. Add one to build the map.</div>}
          <div className="area-list">
            {plan.elements.map((el) => (
              <button key={el.id} className={`area-item ${el.id === selectedId ? "active" : ""}`} onClick={() => setSelectedId(el.id)}>
                {el.name || "(no name)"}<small>{kindOf(el.type).label}</small>
              </button>
            ))}
          </div>
          <button className="btn" style={{ marginTop: 10 }} onClick={add}><Plus size={15} /> Add area</button>
        </div>

        {error && <div className="alert error">{error}</div>}
        <div className="toolbar" style={{ marginBottom: 0 }}>
          <button className="btn" onClick={onCancel}>Cancel</button>
          <span style={{ flex: 1 }} />
          <button className="btn primary" disabled={saving || plan.elements.length === 0} onClick={save}>
            {saving ? <><span className="spinner" /> Saving...</> : "Save and open the map"}
          </button>
        </div>
      </div>
    </div>
  );
}
