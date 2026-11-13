# Lennart
from dataclasses import dataclass

from models.incident import Incident


# What an edit or revert did: status is 'updated', 'unchanged', 'rejected', 'failed' or 'not_saved'.
@dataclass
class EditResult:
    status: str
    incident: Incident | None = None
    previous: Incident | None = None
    message: str | None = None
