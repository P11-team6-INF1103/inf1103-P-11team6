// Ren Xiang
import { useEffect, useRef, useState } from "react";
import { Maximize2, Minus, Plus } from "lucide-react";
import SiteMarks from "./SitePins.jsx";

// Fill and outline for each kind of element, drawn bottom to top so small things are not hidden by big ones.
const LOOK = {
  zone: ["#1c2a27", "#4c6360"], road: ["#2a3331", "#5b6b68"], laydown: ["#2d2a1d", "#8a7d3a"],
  excavation: ["#2b1f1a", "#b4693e"], cabin: ["#1d2b33", "#4f8aa6"], power: ["#2d2a14", "#c9a227"],
  gate: ["#16302a", "#2fd59b"], scaffold: ["#2d2418", "#d08a3a"], building: ["#22302d", "#9fb0ab"],
  tower_crane: ["#2f2a10", "#f5c518"],
};
const ORDER = ["zone", "road", "laydown", "excavation", "cabin", "power", "gate", "building", "scaffold", "tower_crane"];

const MIN_SIDE = 2; // the smallest an area can be dragged to, in metres
const round1 = (n) => Math.round(n * 10) / 10;

// The 2D site map: a flat pin board of the plan. It draws what it is given: the plan, optional pins and heat.
// pins are { id, sev, x, y, label } with x and y in plan metres (y runs down the page). heat is { elementId: count }.
// In editing mode (the review screen) the areas can be selected, dragged to move and resized by their corners:
// editId is the selected area, onSelectElement(id) selects (or null clears), onChangeElement(id, { x, y, w, d }) moves.
export default function SiteMap({
  plan, pins = [], heat = {}, heatOn = true, selectedId = null,
  focus = null, onPick, height = 560, editing = false, editId = null, onSelectElement, onChangeElement,
}) {
  const [tip, setTip] = useState(null);
  const svgRef = useRef(null);
  const W = plan.width_m;
  const D = plan.depth_m;
  const grid = W > 400 || D > 400 ? 100 : W > 120 || D > 120 ? 20 : 10;
  const unit = Math.max(W, D) / 90; // one pin-sized step, so pins keep the same look on a small or a large site
  const peak = Math.max(1, ...Object.values(heat));
  const elements = [...plan.elements].sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type));
  if (editing && editId) elements.sort((a, b) => (a.id === editId) - (b.id === editId)); // the selected area is drawn on top
  const pad = unit * 2;
  const home = { x: -pad, y: -pad, w: W + pad * 2, h: D + pad * 2 };
  // The visible window onto the plan, in plan metres. Dragging the background pans it, the wheel and the buttons zoom it.
  const [view, setView] = useState(home);
  const viewRef = useRef(view);
  viewRef.current = view;
  useEffect(() => { setView({ x: -pad, y: -pad, w: W + pad * 2, h: D + pad * 2 }); }, [W, D, pad]);

  // Keeps part of the plan on screen so it cannot be lost off the edge.
  const clampView = (v) => ({
    ...v,
    x: Math.min(Math.max(v.x, -v.w * 0.8), W - v.w * 0.2),
    y: Math.min(Math.max(v.y, -v.h * 0.8), D - v.h * 0.2),
  });
  // Zooms by factor around a point given as 0..1 across the visible window (0.5, 0.5 is the centre).
  const zoomBy = (factor, fx = 0.5, fy = 0.5) => setView((v) => {
    const w = Math.min(Math.max(v.w * factor, home.w / 12), home.w * 3);
    const h = w * (home.h / home.w);
    return clampView({ x: v.x + (v.w - w) * fx, y: v.y + (v.h - h) * fy, w, h });
  });
  const zoomRef = useRef(zoomBy);
  zoomRef.current = zoomBy;

  // The wheel is attached by hand because React's wheel handler cannot stop the page from scrolling.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      zoomRef.current(Math.exp(e.deltaY * 0.0015), (e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height);
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, []);

  // Dragging empty space (or any area when not editing) moves the view. A click without a drag still clears the selection.
  function startPan(event) {
    if (event.button !== undefined && event.button !== 0) return;
    const svg = svgRef.current;
    const scale = svg.getScreenCTM().a; // screen pixels per plan metre
    const from = viewRef.current;
    const startX = event.clientX;
    const startY = event.clientY;
    let moved = false;
    const move = (e) => {
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      setView(clampView({ ...from, x: from.x - dx / scale, y: from.y - dy / scale }));
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      if (!moved && editing) onSelectElement?.(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  const focused = focus ? elements.find((e) => focus.x >= e.x && focus.x <= e.x + e.w && focus.y >= e.y && focus.y <= e.y + e.d) : null;

  // Starts a drag: mode is "move" or the corner being pulled ("nw", "ne", "sw", "se"). The pointer is followed on the
  // whole window, so the drag keeps working when the pointer leaves the shape.
  function startDrag(event, el, mode) {
    if (!editing) return;
    event.stopPropagation();
    event.preventDefault();
    onSelectElement?.(el.id);
    const svg = svgRef.current;
    const toPlan = (e) => {
      const point = svg.createSVGPoint();
      point.x = e.clientX;
      point.y = e.clientY;
      const at = point.matrixTransform(svg.getScreenCTM().inverse());
      return { x: at.x, y: at.y };
    };
    const start = toPlan(event);
    const from = { x: el.x, y: el.y, w: el.w, d: el.d };
    const move = (e) => {
      const now = toPlan(e);
      const dx = now.x - start.x;
      const dy = now.y - start.y;
      let { x, y, w, d } = from;
      if (mode === "move") {
        x = Math.min(Math.max(from.x + dx, 0), W - w);
        y = Math.min(Math.max(from.y + dy, 0), D - d);
      } else {
        const right = from.x + from.w;
        const bottom = from.y + from.d;
        if (mode.includes("w")) { x = Math.min(Math.max(from.x + dx, 0), right - MIN_SIDE); w = right - x; }
        if (mode.includes("e")) { w = Math.min(Math.max(from.w + dx, MIN_SIDE), W - from.x); }
        if (mode.includes("n")) { y = Math.min(Math.max(from.y + dy, 0), bottom - MIN_SIDE); d = bottom - y; }
        if (mode.includes("s")) { d = Math.min(Math.max(from.d + dy, MIN_SIDE), D - from.y); }
      }
      onChangeElement?.(el.id, { x: round1(x), y: round1(y), w: round1(w), d: round1(d) });
    };
    const stop = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  const show = (data, event) => {
    const rect = event.currentTarget.ownerSVGElement.getBoundingClientRect();
    setTip({ text: data, x: event.clientX - rect.left, y: event.clientY - rect.top });
  };

  return (
    <div className={`site-stage site-map ${editing ? "editing" : ""}`} style={{ height }}>
      <svg ref={svgRef} onPointerDown={startPan} viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} preserveAspectRatio="xMidYMid meet"
           role="img" aria-label={`Map of ${plan.name}`} onMouseLeave={() => setTip(null)}>
        <defs>
          <filter id="site-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation={unit * 3} /></filter>
          <pattern id="site-grid" width={grid} height={grid} patternUnits="userSpaceOnUse">
            <path d={`M ${grid} 0 H 0 V ${grid}`} fill="none" stroke="#24322f" strokeWidth={unit * 0.12} />
          </pattern>
        </defs>

        <rect x="0" y="0" width={W} height={D} fill="#121a19" />
        <rect x="0" y="0" width={W} height={D} fill="url(#site-grid)" />
        <rect x="0" y="0" width={W} height={D} fill="none" stroke="#4c6360" strokeWidth={unit * 0.3} />

        {elements.map((el) => {
          const [fill, line] = LOOK[el.type] || LOOK.zone;
          const small = Math.min(el.w, el.d) < unit * 7;
          return (
            <g key={el.id}>
              {el.type === "tower_crane" && (
                <circle cx={el.x + el.w / 2} cy={el.y + el.d / 2} r={el.radius_m || 30} fill="none" stroke={line}
                        strokeOpacity="0.45" strokeWidth={unit * 0.2} strokeDasharray={`${unit * 1.2} ${unit * 0.8}`} />
              )}
              <rect x={el.x} y={el.y} width={el.w} height={el.d} rx={unit * 0.4} fill={fill}
                    stroke={focused?.id === el.id || editId === el.id ? "#e9efed" : line}
                    strokeWidth={focused?.id === el.id || editId === el.id ? unit * 0.5 : unit * 0.25}
                    style={editing ? { cursor: "move" } : undefined}
                    onPointerDown={(e) => startDrag(e, el, "move")}
                    onMouseMove={(e) => !editing && show(`${el.name}${heat[el.id] ? ` · ${heat[el.id]} incident${heat[el.id] === 1 ? "" : "s"}` : ""}`, e)}
                    onMouseLeave={() => setTip(null)} />
              {!small && (
                <text x={el.x + unit * 0.9} y={el.y + unit * 2.6} fontSize={unit * 2.1} fontWeight="700" fill="#e9efed"
                      style={{ pointerEvents: "none", textTransform: "uppercase" }}>{String(el.name).slice(0, 22)}</text>
              )}
              {editing && editId === el.id && [["nw", el.x, el.y], ["ne", el.x + el.w, el.y], ["sw", el.x, el.y + el.d], ["se", el.x + el.w, el.y + el.d]].map(([corner, cx, cy]) => (
                <rect key={corner} className="site-handle" x={cx - unit * 0.9} y={cy - unit * 0.9} width={unit * 1.8} height={unit * 1.8} rx={unit * 0.3}
                      style={{ cursor: `${corner === "nw" || corner === "se" ? "nwse" : "nesw"}-resize` }}
                      onPointerDown={(e) => startDrag(e, el, corner)} />
              ))}
            </g>
          );
        })}

        <SiteMarks elements={elements} pins={pins} heat={heat} heatOn={heatOn} peak={peak} unit={unit} selectedId={selectedId}
                   onPick={onPick} show={show} hide={() => setTip(null)} />
      </svg>
      <div className="site-zoom" onPointerDown={(e) => e.stopPropagation()}>
        <button type="button" aria-label="Zoom in" onClick={() => zoomBy(1 / 1.4)}><Plus size={16} /></button>
        <button type="button" aria-label="Zoom out" onClick={() => zoomBy(1.4)}><Minus size={16} /></button>
        <button type="button" aria-label="Fit the whole site" onClick={() => setView(home)}><Maximize2 size={14} /></button>
      </div>
      {tip && <div className="site-tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
      <div className="site-hint">{editing
        ? "Click an area to select it · drag it to move · drag a corner to resize · drag empty space to pan · scroll to zoom"
        : `Top-down plan · drag to pan · scroll to zoom · hotspots glow red where incidents cluster${pins.length ? " · click a pin to open the incident" : ""}`}</div>
    </div>
  );
}