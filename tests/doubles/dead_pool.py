# Lennart
from contextlib import contextmanager

from psycopg_pool import PoolTimeout

from tests.doubles.fake_pool import FakePool


class DeadPool(FakePool):
    # A Postgres server that never answers: the pool gives up waiting for a connection.
    @contextmanager
    def connection(self):
        raise PoolTimeout("couldn't get a connection after 10.00 sec")
        yield  # pragma: no cover
