// Darrel
// Display names and colours shared by every page.
// Wording comes from the backend (/api/meta) when available so it matches the terminal app.

export const SEVERITY_COLORS = {
  0: "#7d8a87",
  1: "#2fd59b",
  2: "#a3e635",
  3: "#facc15",
  4: "#fb923c",
  5: "#f87171",
};

export const OUTCOME_COLORS = {
  stop_work_review: "#f87171",
  photo_review: "#c084fc",
  systemic_escalation: "#fb923c",
  pending_review: "#facc15",
  log_only: "#2fd59b",
};

export const PRIORITY_COLORS = { 1: "#f87171", 2: "#fb923c", 3: "#facc15", 4: "#7d8a87" };

export const HAZARD_COLORS = ["#2fd59b", "#1f9d74", "#7de8c3", "#38bdf8", "#facc15", "#fb923c", "#f87171", "#c084fc"];

// Fallbacks used until /api/meta has loaded.
export const DEFAULT_META = {
  outcome_names: {
    stop_work_review: "STOP WORK - safety review",
    photo_review: "CHECK PHOTO",
    systemic_escalation: "ESCALATE to management",
    log_only: "LOG ONLY",
    pending_review: "NEEDS MANUAL REVIEW",
  },
  hazard_names: {},
  priority_levels: { 1: "Urgent", 2: "High", 3: "Normal", 4: "Low" },
  outcome_actions: {},
  severity_levels: {},
};

export function formatDate(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return String(timestamp);
  return date.toLocaleString("en-SG", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
