# Daniel
import re


class IncidentSearch:
    # Ranked free-text search over incidents as the browser sees them (the dicts from WebApi._to_json).
    # Every search word must match somewhere (AND); a word matches the start of any word in a field.
    # "double quotes" search for an exact phrase, and #12 or 12 finds incident number 12.

    # How much a match in each field is worth.
    FIELD_WEIGHTS = {
        "description": 4.0, "location": 3.0, "hazard": 3.0, "causes": 1.5, "actions": 1.0,
        "reporter": 1.0, "resolution": 1.0, "photo": 0.5, "sources": 0.5,
    }
    _QUERY_PARTS = re.compile(r'"([^"]+)"|(\S+)')
    _WORD = re.compile(r"[a-z0-9]+")

    def __init__(self, hazard_names: dict[str, str] | None = None) -> None:
        self._hazard_names = hazard_names or {}

    def _fields(self, incident: dict) -> dict[str, str]:
        hazard = incident.get("hazard_type") or ""
        sources = " ".join(str(w.get("summary", "")) for w in incident.get("web_incidents") or [] if isinstance(w, dict))
        return {
            "description": str(incident.get("description") or ""),
            "location": str(incident.get("location") or ""),
            "hazard": f"{hazard} {self._hazard_names.get(hazard, '')} {incident.get('hazard_category') or ''}",
            "causes": " ".join(map(str, incident.get("review_likely_causes") or [])),
            "actions": " ".join(map(str, incident.get("review_prevention_actions") or [])),
            "reporter": f"{incident.get('reporter_role') or ''} {incident.get('reported_by') or ''}",
            "resolution": str(incident.get("resolution_note") or ""),
            "photo": " ".join(str(v) for v in (incident.get("photo_description"), incident.get("photo_findings")) if v),
            "sources": sources,
        }

    # (phrases, words) the user typed, all lower case.
    def _parse(self, query: str) -> tuple[list[str], list[str]]:
        phrases, words = [], []
        for phrase, word in self._QUERY_PARTS.findall(query.lower()):
            if phrase:
                phrases.append(" ".join(self._WORD.findall(phrase)))
            else:
                words.extend(self._WORD.findall(word))
        return [p for p in phrases if p], words

    def _word_score(self, term: str, fields: dict[str, list[str]]) -> tuple[float, list[str]]:
        stem = term[:-1] if len(term) > 3 and term.endswith("s") else term
        score, hit = 0.0, []
        for name, tokens in fields.items():
            if any(token.startswith(stem) for token in tokens):
                score += self.FIELD_WEIGHTS[name] * (1.5 if term in tokens else 1.0)
                hit.append(name)
        return score, hit

    def _passes(self, incident: dict, filters: dict) -> bool:
        severity = 0 if incident.get("assessment_error") else int(incident.get("severity_estimate") or 0)
        day = str(incident.get("timestamp") or "")[:10]
        checks = [
            filters.get("severity_min") is None or severity >= filters["severity_min"],
            not filters.get("hazard") or incident.get("hazard_type") == filters["hazard"],
            not filters.get("outcome") or incident.get("outcome") == filters["outcome"],
            not filters.get("location") or str(incident.get("location", "")).lower() == filters["location"].lower(),
            filters.get("priority") is None or incident.get("priority") == filters["priority"],
            not filters.get("status") or incident.get("resolved") == (filters["status"] == "resolved"),
            not filters.get("date_from") or day >= filters["date_from"],
            not filters.get("date_to") or day <= filters["date_to"],
            not filters.get("has_photo") or bool(incident.get("photo_file")),
        ]
        return all(checks)

    # Matching incidents, best match first (newest first when there is no query). Each result is the
    # incident plus 'score' and 'matched' (the fields the words were found in).
    def search(self, incidents: list[dict], query: str = "", filters: dict | None = None) -> list[dict]:
        phrases, words = self._parse(query or "")
        results = []
        for incident in incidents:
            if not self._passes(incident, filters or {}):
                continue
            fields = self._fields(incident)
            tokens = {name: self._WORD.findall(text.lower()) for name, text in fields.items()}
            score, matched, found_all = 0.0, set(), True
            for term in words:
                if term.isdigit() and int(term) == incident.get("id"):
                    score, found_all = score + 10, True
                    matched.add("id")
                    continue
                word_score, hit = self._word_score(term, tokens)
                if not hit:
                    found_all = False
                    break
                score += word_score
                matched.update(hit)
            for phrase in phrases if found_all else []:
                hit = [name for name, tokens_ in tokens.items() if phrase in " ".join(tokens_)]
                if not hit:
                    found_all = False
                    break
                score += 2 * sum(self.FIELD_WEIGHTS[name] for name in hit)
                matched.update(hit)
            if found_all:
                results.append({**incident, "score": round(score, 2), "matched": sorted(matched)})
        if not words and not phrases:
            results.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        else:
            results.sort(key=lambda r: (r["score"], str(r.get("timestamp") or "")), reverse=True)
        return results
