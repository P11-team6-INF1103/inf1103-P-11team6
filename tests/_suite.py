"""Shared test helpers. The project bans class definitions, so tests are
plain test_* functions and each test module's load_tests() wraps them in
unittest.FunctionTestCase (a ready-made class from the standard library)."""

import contextlib
import functools
import io
import logging
import os
import tempfile
import unittest
from unittest import mock


def _offline(test):
    """Runs `test` with no API keys and every network call blocked, so a
    unit test can never spend quota or depend on the internet."""
    @functools.wraps(test)
    def run():
        def blocked(*args, **kwargs):
            raise AssertionError("test tried to use the network")
        keys = {"GEMINI_API_KEY": "", "GROQ_API_KEY": "", "GOOGLE_API_KEY": ""}
        with mock.patch.dict(os.environ, keys), \
                mock.patch("requests.get", blocked), mock.patch("requests.post", blocked):
            test()
    return run


def suite_from(namespace):
    """Builds a suite from every test_* function in `namespace`, each run
    offline (see _offline)."""
    suite = unittest.TestSuite()
    for name in sorted(namespace):
        if name.startswith("test_") and callable(namespace[name]):
            suite.addTest(unittest.FunctionTestCase(_offline(namespace[name]), description=name))
    return suite


@contextlib.contextmanager
def temp_data_dir():
    """Points INCIDENT_DATA_DIR at a fresh empty folder for one test."""
    with tempfile.TemporaryDirectory() as folder:
        with mock.patch.dict(os.environ, {"INCIDENT_DATA_DIR": folder}):
            yield folder


@contextlib.contextmanager
def typed(lines):
    """Feeds `lines` to input(), one per call; raises EOFError when they
    run out (like a closed stdin). Yields the captured stdout buffer."""
    feed = iter(lines)

    def fake_input(prompt=""):
        print(prompt, end="")
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    buffer = io.StringIO()
    with mock.patch("builtins.input", fake_input), contextlib.redirect_stdout(buffer):
        yield buffer


@contextlib.contextmanager
def captured_logs(name):
    """Collects the messages logged to logger `name`."""
    messages = []
    handler = logging.Handler()
    handler.emit = lambda record: messages.append(record.getMessage())
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    try:
        yield messages
    finally:
        logger.removeHandler(handler)