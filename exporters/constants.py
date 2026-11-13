# Lennart

# The columns of an export, in order. Each is read from the saved incident by IncidentExporter.row().
COLUMNS = (
    "number", "version", "logged_at", "location", "reporter_role", "injury", "hazard", "severity",
    "outcome", "recurrence", "ppe_status", "description", "severity_reasons", "prevention_actions",
)

# A spreadsheet treats a cell that starts with one of these as a formula, so the CSV exporter puts a ' in front.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")

# Separates the items of a list (reasons, actions) inside one CSV cell.
LIST_SEPARATOR = " | "
