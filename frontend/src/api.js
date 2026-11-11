// Lennart
// All calls to the Flask backend (web_api.py) live here.
const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(API_URL + path, options);
  } catch {
    throw new Error("Cannot reach the server. If it is on Render's free plan it may take a minute to wake up.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.rejected ? `Rejected: ${body.rejected}` : (body.errors || ["Request failed"]).join(" · "));
    error.body = body;
    throw error;
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),
  meta: () => request("/api/meta"),
  incidents: () => request("/api/incidents"),
  // form is a FormData with description, location, reporter_role, injury and an optional photo file
  incident: (id) => request(`/api/incidents/${id}`),
  createIncident: (form) => request("/api/incidents", { method: "POST", body: form }),
  // form is a FormData with any of the same fields, plus remove_photo=true; the AI runs again if anything changed
  editIncident: (id, form) => request(`/api/incidents/${id}`, { method: "PATCH", body: form }),
  revertIncident: (id, version) => request(`/api/incidents/${id}/revert`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version }),
  }),
  deleteIncident: (id) => request(`/api/incidents/${id}`, { method: "DELETE" }),
  // version is optional: leave it out for the current photo
  photoUrl: (id, version) => `${API_URL}/api/incidents/${id}/photo${version ? `?version=${version}` : ""}`,
  // params: q, severity_min, hazard, outcome, location, priority, status, date_from, date_to, has_photo
  search: (params) => request(`/api/incidents/search?${new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v !== false && v != null)).toString()}`),
  setPriority: (id, priority) => request(`/api/incidents/${id}/priority`, json("PUT", { priority })),
  resolveIncident: (id, note) => request(`/api/incidents/${id}/resolve`, json("POST", { note })),
  reopenIncident: (id) => request(`/api/incidents/${id}/reopen`, { method: "POST" }),
  // The trend and summary report for the last `days` days; the CSV link downloads the same report.
  summary: (days) => request(`/api/reports/summary?days=${days}`),
  summaryCsvUrl: (days) => `${API_URL}/api/reports/summary?days=${days}&format=csv`,
  queryLocation: (location, days) =>
    request(`/api/locations/query?location=${encodeURIComponent(location)}&days=${days}`),
  // The site map: the saved plan, a draft read from a plan image (nothing saved yet), save, delete, downloads.
  sitePlan: () => request("/api/site-plan"),
  // form is a FormData with plan (image file), site_width_m, image_aspect and an optional site_name
  readSitePlan: (form) => request("/api/site-plan/read", { method: "POST", body: form }),
  saveSitePlan: (plan) => request("/api/site-plan", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(plan),
  }),
  deleteSitePlan: () => request("/api/site-plan", { method: "DELETE" }),
  // name is json, blank, sample or guide
};
