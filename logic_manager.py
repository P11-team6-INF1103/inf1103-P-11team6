def is_high_severity(record):
    """Rule 1 (severity): severity_estimate >= 4 OR (injury AND
    likelihood_recurrence == 'high') — evaluated against Daniel's
    judgment."""
    severity = record.get("severity_estimate", 0)
    injury = record.get("injury", False)
    recurrence = record.get("likelihood_recurrence", "unknown")
    return severity >= 4 or (injury and recurrence == "high")
