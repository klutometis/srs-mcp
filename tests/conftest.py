"""Force the SQLite backend at a throwaway path, before srs_mcp is imported.

srs_mcp picks its backend at import time from the environment, so this has to
run first -- conftest is imported before any test module. Without it a
developer with SRS_DATABASE_URL set in their shell would point the suite at
the shared Neon deck and wipe it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.pop("SRS_DATABASE_URL", None)
os.environ.pop("DATABASE_URL", None)
os.environ["SRS_DB"] = str(Path(tempfile.mkdtemp(prefix="srs-tests-")) / "srs.db")

import pytest  # noqa: E402

import srs_mcp  # noqa: E402


@pytest.fixture(autouse=True)
def clean_deck():
    """Empty the card box between tests."""
    with srs_mcp._db() as conn:
        conn.execute("DELETE FROM cards")
    yield
