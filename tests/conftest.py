"""
Test-session configuration.

Points the SQLite store at a throwaway file BEFORE any apps module is
imported, so unit tests never read or pollute the real database under
data/. Each pytest session starts from a fresh chain.
"""
import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "sellable-test.db")
for _suffix in ("", "-wal", "-shm"):
    try:
        if os.path.exists(_TEST_DB + _suffix):
            os.remove(_TEST_DB + _suffix)
    except OSError:
        pass

os.environ["SELLABLE_DB_PATH"] = _TEST_DB
