"""Test harness: every test runs against a fresh copy of tests/fixtures/root.

`harness.paths` resolves HARNESS_ROOT once at import time, so the root is
fixed for the session and its *contents* are reset before each test.
"""
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "root"
ROOT = Path(tempfile.mkdtemp(prefix="harness-test-"))
os.environ["HARNESS_ROOT"] = str(ROOT)  # must precede any `harness` import


@pytest.fixture(autouse=True)
def harness_root():
    shutil.rmtree(ROOT, ignore_errors=True)
    shutil.copytree(FIXTURE_ROOT, ROOT)
    from harness import paths
    paths.ensure_dirs()
    yield ROOT


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(ROOT, ignore_errors=True)
