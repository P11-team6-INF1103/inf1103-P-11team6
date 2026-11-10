# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".

class RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return "cursor"
