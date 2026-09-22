"""Tests for routers/auth.py — /auth/signup and /auth/login.

routers/auth.py shares its database path, "helpers" table schema, password
hashing, and in-memory token store with main.py's /helpers/* handlers via
auth_shared.py (see auth_shared.py's module docstring for why). Every test
here redirects auth_shared.DB_PATH to a fresh temp-file database, and clears
auth_shared.helper_tokens afterward, so tests stay isolated from each other
and from a real helpers.db file wherever pytest happens to run from.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import auth_shared
from routers import auth


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirect auth_shared.DB_PATH to a temp file, and clear the shared
    in-memory token store afterward so tests don't leak tokens into each
    other via that module-level dict."""
    db_path = tmp_path / "helpers_test.db"
    monkeypatch.setattr(auth_shared, "DB_PATH", db_path)
    yield db_path
    auth_shared.helper_tokens.clear()


def make_body(email="new.helper@example.com", password="correct horse battery staple", name=None):
    return auth.AuthBody(email=email, password=password, name=name)


class TestSignup:
    def test_creates_new_account_successfully(self, isolated_db):
        result = auth.signup(make_body())
        assert result == {"ok": True}

    def test_duplicate_email_raises_409(self, isolated_db):
        auth.signup(make_body(email="dupe@example.com"))
        with pytest.raises(HTTPException) as exc_info:
            auth.signup(make_body(email="dupe@example.com", password="a different password"))
        assert exc_info.value.status_code == 409

    def test_same_email_different_case_is_treated_as_distinct(self, isolated_db):
        # Documents current behavior: email uniqueness is a raw TEXT UNIQUE
        # column, so "a@b.com" and "A@b.com" are NOT treated as the same
        # account. Not asserting this is correct — just that it's what
        # happens today.
        auth.signup(make_body(email="case@example.com"))
        result = auth.signup(make_body(email="Case@example.com"))
        assert result == {"ok": True}

    def test_password_is_stored_hashed_not_plaintext(self, isolated_db):
        password = "correct horse battery staple"
        auth.signup(make_body(email="hash-check@example.com", password=password))
        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT password_hash FROM helpers WHERE email=?", ("hash-check@example.com",)).fetchone()
        assert row[0] != password

    def test_same_password_hashes_differently_per_account_due_to_salting(self, isolated_db):
        # The real proof the fix works: two accounts with the identical
        # password must not produce the identical stored hash, since each
        # gets its own random salt. Unsalted SHA-256 would fail this.
        auth.signup(make_body(email="salt-a@example.com", password="hunter2"))
        auth.signup(make_body(email="salt-b@example.com", password="hunter2"))
        conn = sqlite3.connect(isolated_db)
        hash_a = conn.execute("SELECT password_hash FROM helpers WHERE email=?", ("salt-a@example.com",)).fetchone()[0]
        hash_b = conn.execute("SELECT password_hash FROM helpers WHERE email=?", ("salt-b@example.com",)).fetchone()[0]
        assert hash_a != hash_b

    def test_uses_the_canonical_helpers_schema(self, isolated_db):
        # Proves this router writes into the same table shape as main.py's
        # /helpers/signup, not a second, divergent (email/pw/salt) table.
        auth.signup(make_body(email="schema-check@example.com"))
        conn = sqlite3.connect(isolated_db)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(helpers)")}
        assert {"id", "name", "email", "password_hash"} <= columns

    def test_missing_name_falls_back_to_email_local_part(self, isolated_db):
        auth.signup(make_body(email="no-name@example.com", name=None))
        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT name FROM helpers WHERE email=?", ("no-name@example.com",)).fetchone()
        assert row[0] == "no-name"

    def test_explicit_name_is_used_when_supplied(self, isolated_db):
        auth.signup(make_body(email="named@example.com", name="Real Name"))
        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT name FROM helpers WHERE email=?", ("named@example.com",)).fetchone()
        assert row[0] == "Real Name"


class TestLogin:
    def test_correct_credentials_returns_ok_and_token(self, isolated_db):
        auth.signup(make_body(email="login-ok@example.com", password="hunter2"))
        result = auth.login(make_body(email="login-ok@example.com", password="hunter2"))
        assert result["ok"] is True
        assert isinstance(result["token"], str)

    def test_unknown_email_raises_401(self, isolated_db):
        auth.signup(make_body(email="someone-else@example.com", password="hunter2"))
        with pytest.raises(HTTPException) as exc_info:
            auth.login(make_body(email="never-signed-up@example.com", password="whatever"))
        assert exc_info.value.status_code == 401

    def test_login_on_a_never_used_database_returns_clean_401(self, isolated_db):
        # login() ensures the table exists before querying it, so a fresh
        # deployment (or a fresh temp DB, as here) fails safely with 401
        # rather than an unhandled sqlite3.OperationalError.
        with pytest.raises(HTTPException) as exc_info:
            auth.login(make_body(email="anyone@example.com", password="whatever"))
        assert exc_info.value.status_code == 401

    def test_wrong_password_raises_401(self, isolated_db):
        auth.signup(make_body(email="wrong-pw@example.com", password="correct-password"))
        with pytest.raises(HTTPException) as exc_info:
            auth.login(make_body(email="wrong-pw@example.com", password="incorrect-password"))
        assert exc_info.value.status_code == 401

    def test_each_login_issues_a_different_token(self, isolated_db):
        auth.signup(make_body(email="two-tokens@example.com", password="hunter2"))
        first = auth.login(make_body(email="two-tokens@example.com", password="hunter2"))
        second = auth.login(make_body(email="two-tokens@example.com", password="hunter2"))
        assert first["token"] != second["token"]

    def test_issued_token_is_stored_in_the_shared_token_store(self, isolated_db):
        # Previously login() persisted tokens into a separate SQLite table
        # nothing else ever checked. It now writes into the exact same
        # in-memory dict main.py's /helpers/me and /helpers/delete-account
        # read from, via auth_shared.helper_tokens.
        auth.signup(make_body(email="token-stored@example.com", password="hunter2"))
        result = auth.login(make_body(email="token-stored@example.com", password="hunter2"))

        conn = sqlite3.connect(isolated_db)
        helper_id = conn.execute(
            "SELECT id FROM helpers WHERE email=?", ("token-stored@example.com",)
        ).fetchone()[0]

        assert auth_shared.helper_tokens.get(result["token"]) == helper_id
