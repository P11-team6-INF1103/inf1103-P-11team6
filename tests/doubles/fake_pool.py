# Lennart
from contextlib import contextmanager

from tests.doubles.recording_connection import RecordingConnection


class FakePool:
    instances = []
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
