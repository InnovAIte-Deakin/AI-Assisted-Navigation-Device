"""Shared canonical auth state for main.py's /helpers/* handlers and routers/auth.py.

Both main.py and routers/auth.py need the same SQLite database path, the
same "helpers" table schema, the same password hashing scheme, and the
same in-memory token store -- otherwise two auth code paths pointed at the
same physical database file fight over incompatible schemas, and a token
issued by one path can never be validated by the other. This module is the
single source of truth for all four, so any router that authenticates a
helper reuses exactly the same implementation main.py always has.

main.py imports from here instead of defining these locally to avoid a
circular import (main.py imports routers.auth, so routers.auth cannot
import main.py back).
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "helpers.db"

# In-memory token store: token -> helper_id. Shared by every router that
# issues or validates a helper auth token, so a token from one login path
# validates correctly against any other route that checks identity.
helper_tokens: dict[str, int] = {}

PBKDF2_ITERATIONS = 260_000


def init_database(db_path: Path | str | None = None) -> None:
    """Create the canonical helpers table if it does not already exist.

    Safe to call from multiple places (CREATE TABLE IF NOT EXISTS is
    idempotent) -- every router that touches the helpers table should call
    this before its first query, the same way main.py always has.

    ``db_path`` defaults to the module-level DB_PATH, read at call time
    (not baked in as a default-argument value) -- a default of ``= DB_PATH``
    would bind the path this module had at import time and silently ignore
    a test (or caller) that later reassigns ``auth_shared.DB_PATH``.
    """
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS helpers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                age INTEGER,
                phone TEXT,
                address TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                experience_level TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """Salted PBKDF2-HMAC-SHA256, stored as "salt:hash" in a single column."""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
        return secrets.compare_digest(hashed, expected)
    except Exception:
        return False
