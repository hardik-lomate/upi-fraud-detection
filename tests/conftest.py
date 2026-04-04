import os
from pathlib import Path


def pytest_sessionstart(session):
    """Ensure tests run against an isolated SQLite DB file."""
    os.environ.setdefault("AUTH_REQUIRED", "false")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only-32chars")

    # Keep tests isolated from the demo DB.
    test_db_path = Path(__file__).resolve().parent.parent / ".pytest_fraud_detection.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{test_db_path.as_posix()}")

    if test_db_path.exists():
        test_db_path.unlink()
