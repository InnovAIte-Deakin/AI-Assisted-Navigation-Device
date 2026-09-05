"""Tests for routers/auth.py — /auth/signup and /auth/login.

auth.py connects to a real SQLite file at a hardcoded relative path
("helpers.db"). To keep tests isolated and avoid creating/polluting a real
database file wherever pytest happens to run from, every test redirects
sqlite3.connect() to a fresh temp-file database via the isolated_db fixture.

Scope note: this file tests auth.py's *current* behavior as-is. It does not
fix the known issues (unsalted SHA-256 hashing, and login tokens that are
generated but never stored anywhere a later request could validate) — those
are tracked separately. Documenting current behavior here (including its
gaps) is deliberate, not an oversight.
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

from routers import auth


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirect auth.py's hardcoded sqlite3.connect("helpers.db") to a temp file.

    Without this, every test run would create/reuse a real helpers.db file
    in the current working directory, and tests would leak state into each
    other (e.g. "duplicate email" from a previous run).
    """
    db_path = str(tmp_path / "helpers_test.db")
    real_connect = sqlite3.connect
    monkeypatch.setattr(auth.sqlite3, "connect", lambda _path: real_connect(db_path))
    return db_path


def make_body(email="new.helper@example.com", password="correct horse battery staple"):
    return auth.AuthBody(email=email, password=password)


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
        row = conn.execute("SELECT pw FROM helpers WHERE email=?", ("hash-check@example.com",)).fetchone()
        assert row[0] != password


class TestLogin:
    def test_correct_credentials_returns_ok_and_token(self, isolated_db):
        auth.signup(make_body(email="login-ok@example.com", password="hunter2"))
        result = auth.login(make_body(email="login-ok@example.com", password="hunter2"))
        assert result["ok"] is True
        assert isinstance(result["token"], str)
        assert len(result["token"]) == 64  # secrets.token_hex(32) -> 64 hex chars

    def test_unknown_email_raises_401(self, isolated_db):
        # login() doesn't create the table itself (only signup() does), so an
        # unrelated signup seeds it first — isolating this test to the
        # "unknown email" case rather than the fresh-database case below.
        auth.signup(make_body(email="someone-else@example.com", password="hunter2"))
        with pytest.raises(HTTPException) as exc_info:
            auth.login(make_body(email="never-signed-up@example.com", password="whatever"))
        assert exc_info.value.status_code == 401

    def test_login_on_a_never_used_database_crashes_instead_of_401(self, isolated_db):
        # Known gap, not fixed here: signup() runs CREATE TABLE IF NOT
        # EXISTS, but login() does not. If /login is ever called before any
        # /signup has happened on a given deployment, the table doesn't
        # exist yet and this raises an unhandled sqlite3.OperationalError
        # (-> 500) instead of the intended 401 "Invalid credentials".
        with pytest.raises(sqlite3.OperationalError):
            auth.login(make_body(email="anyone@example.com", password="whatever"))

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

    def test_issued_token_is_not_persisted_anywhere(self, isolated_db):
        # Documents a known gap (not fixed in this PR): login() generates a
        # token but never stores it, so no later request could ever
        # validate it against anything. This test fails if a future change
        # accidentally starts persisting tokens without updating this note.
        auth.signup(make_body(email="token-not-stored@example.com", password="hunter2"))
        auth.login(make_body(email="token-not-stored@example.com", password="hunter2"))
        conn = sqlite3.connect(isolated_db)
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert table_names == {"helpers"}  # no separate token/session table exists
