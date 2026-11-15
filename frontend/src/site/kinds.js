// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
// The kinds of element on a site plan, as the review table needs them. Keep in step with ELEMENT_KINDS in site_plan/element_kinds.py.
export const KINDS = [
  { key: "building", label: "Building / tower" },
  { key: "tower_crane", label: "Tower crane" },
  { key: "excavation", label: "Excavation / pit" },
  { key: "scaffold", label: "Scaffold" },
  { key: "cabin", label: "Site office / cabins" },
  { key: "laydown", label: "Laydown / storage" },
  { key: "gate", label: "Gate / entrance" },
  { key: "road", label: "Road / access route" },
  { key: "power", label: "Switchroom / generators" },
  { key: "zone", label: "Other area" },
];

export const kindOf = (key) => KINDS.find((k) => k.key === key) || KINDS[KINDS.length - 1];

// A plan the map can draw: every number a real number inside the site. Used for the live preview while the user
// is still editing, so half-typed values never break the picture.
export function drawablePlan(plan) {
  const num = (v, fallback) => (Number.isFinite(Number(v)) && v !== "" && v !== null ? Number(v) : fallback);
  const width = Math.min(2000, Math.max(20, num(plan.width_m, 90)));
  const depth = Math.min(2000, Math.max(20, num(plan.depth_m, 56)));
  const elements = (plan.elements || []).map((el, n) => {
    const kind = kindOf(el.type);
    const w = Math.min(width, Math.max(1, num(el.w, 5)));
    const d = Math.min(depth, Math.max(1, num(el.d, 5)));
    return {
      ...el, id: el.id || `e${n + 1}`, type: kind.key, name: String(el.name || kind.label), w, d,
      x: Math.min(Math.max(num(el.x, 0), 0), width - w), y: Math.min(Math.max(num(el.y, 0), 0), depth - d),
      radius_m: kind.key === "tower_crane" ? Math.min(100, Math.max(5, num(el.radius_m, 30))) : undefined,
    };
  });
  return { name: plan.name || "Construction site", width_m: width, depth_m: depth, elements };
}
