# Darrel

# Raised by a prompt when the user types /undo or /redo while filling in an incident.
class DraftCommand(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name
