"""Tests for routers/auth.py — /auth/signup and /auth/login.

auth.py connects to a real SQLite file at a hardcoded relative path
("helpers.db"). To keep tests isolated and avoid creating/polluting a real
database file wherever pytest happens to run from, every test redirects
sqlite3.connect() to a fresh temp-file database via the isolated_db fixture.
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

    def test_same_password_hashes_differently_per_account_due_to_salting(self, isolated_db):
        # The real proof the fix works: two accounts with the identical
        # password must not produce the identical stored hash, since each
        # gets its own random salt. Unsalted SHA-256 would fail this.
        auth.signup(make_body(email="salt-a@example.com", password="hunter2"))
        auth.signup(make_body(email="salt-b@example.com", password="hunter2"))
        conn = sqlite3.connect(isolated_db)
        hash_a = conn.execute("SELECT pw FROM helpers WHERE email=?", ("salt-a@example.com",)).fetchone()[0]
        hash_b = conn.execute("SELECT pw FROM helpers WHERE email=?", ("salt-b@example.com",)).fetchone()[0]
        assert hash_a != hash_b


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

    def test_login_on_a_never_used_database_returns_clean_401(self, isolated_db):
        # Previously this crashed with an unhandled sqlite3.OperationalError
        # (-> 500) because only signup() created the table. login() now
        # ensures the table exists too, so a fresh deployment fails safely.
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

    def test_issued_token_is_persisted_and_linked_to_the_right_helper(self, isolated_db):
        # Previously login() generated a token but never stored it anywhere,
        # so no later request could ever validate it. It's now persisted
        # against the helper it belongs to.
        auth.signup(make_body(email="token-stored@example.com", password="hunter2"))
        result = auth.login(make_body(email="token-stored@example.com", password="hunter2"))

        conn = sqlite3.connect(isolated_db)
        helper_id = conn.execute(
            "SELECT id FROM helpers WHERE email=?", ("token-stored@example.com",)
        ).fetchone()[0]
        stored = conn.execute(
            "SELECT helper_id FROM helper_tokens WHERE token=?", (result["token"],)
        ).fetchone()

        assert stored is not None
        assert stored[0] == helper_id
