// Sufi
// Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
// Puts incidents on the site plan. It mirrors SitePlan.find_element in site_plan.py, so the dashboard and the
// server agree on which element a location text refers to. Pure functions, no browser code.

// True if the location text refers to this element (name or alias; short names only match exactly).
export function elementMatches(element, location) {
  const text = String(location || "").trim().toLowerCase();
  if (!text) return false;
  const names = [element.name, ...(element.aliases || [])].map((n) => String(n).toLowerCase());
  return names.some((n) => n === text || (n.length >= 3 && (text.includes(n) || n.includes(text))));
}

// The element a location refers to, or null. An exact name or alias beats a partial match.
export function findElement(plan, location) {
  const text = String(location || "").trim().toLowerCase();
  const matches = (plan?.elements || []).filter((e) => elementMatches(e, text));
  const exact = matches.filter((e) => e.name.toLowerCase() === text || (e.aliases || []).some((a) => a.toLowerCase() === text));
  return exact[0] || matches[0] || null;
}

// A repeatable number from 0 to 1 for a seed, so a pin stays in the same place on every render.
export function steady(seed, salt) {
  let h = 2166136261 ^ (Number(seed) * 2654435761 + salt * 97);
  h = Math.imul(h ^ (h >>> 15), 2246822519);
  h = Math.imul(h ^ (h >>> 13), 3266489917);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// Where inside an element an incident is drawn, in plan metres. The spot is steady, so a pin stays put on every render.
export function pinSpot(element, incidentId) {
  const inset = (size) => Math.min(size * 0.2, 3);
  return {
    x: element.x + inset(element.w) + steady(incidentId, 1) * (element.w - 2 * inset(element.w)),
    y: element.y + inset(element.d) + steady(incidentId, 2) * (element.d - 2 * inset(element.d)),
  };
}

// Splits incidents into the ones that can be pinned on the plan and the ones whose location matches nothing.
export function placeIncidents(plan, incidents) {
  const placed = [];
  const unplaced = [];
  for (const incident of incidents) {
    const element = findElement(plan, incident.location);
    if (element) placed.push({ incident, element, spot: pinSpot(element, incident.id) });
    else unplaced.push(incident);
  }
  return { placed, unplaced };
}

// The severity of an incident for pinning (0 when the AI could not assess it).
export function severityOf(incident) {
  return incident.assessment_error ? 0 : incident.severity_estimate || 0;
}
