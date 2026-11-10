# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
from contextlib import contextmanager

from psycopg_pool import PoolTimeout

from tests.doubles.fake_pool import FakePool


class DeadPool(FakePool):
    # A Postgres server that never answers: the pool gives up waiting for a connection.
    @contextmanager
    def connection(self):
        raise PoolTimeout("couldn't get a connection after 10.00 sec")
        yield  # pragma: no cover
