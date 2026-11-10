# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
from contextlib import contextmanager
from typing import ClassVar

from tests.doubles.recording_connection import RecordingConnection


class FakePool:
    instances: ClassVar[list] = []
    check_connection = staticmethod(lambda connection: None)

    def __init__(self, target, **options):
        self.target, self.options, self.closed = target, options, False
        self.recorder = RecordingConnection()
        FakePool.instances.append(self)

    @contextmanager
    def connection(self):
        yield self.recorder

    def close(self):
        self.closed = True
