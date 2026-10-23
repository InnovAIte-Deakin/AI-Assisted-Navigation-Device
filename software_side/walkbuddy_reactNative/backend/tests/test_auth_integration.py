"""Real-app integration tests for /auth/* and /helpers/* against the actual app.

Unlike test_auth.py (which calls auth.signup()/auth.login() as plain Python
functions against an isolated temp database), these tests import the actual
`main.app` -- with every router mounted exactly as production does -- and
reproduce the specific integration concerns raised in review of this PR:

  * The real backend startup runs main.py's init_database(), which creates
    helpers.db with the canonical schema (name/email/password_hash/...)
    *before* any request is served. routers/auth.py must not fail against
    that already-created table, and must not create a second, divergent
    database file.
  * A token issued by POST /auth/login must validate against the existing
    GET /helpers/me path -- there must be one coherent token store, not
    two incompatible auth systems.
  * main.py used to also register a second, legacy /helpers/signup and
    /helpers/login (routers/helpers.py: an in-memory, non-persistent,
    unsalted-plaintext-password implementation) that silently shadowed
    this file's own /helpers/* handlers -- the frontend's real traffic was
    actually being served by that legacy implementation, not the canonical
    one. That router has been removed entirely; this file asserts exactly
    one handler is registered per /helpers/* path, and exercises the real
    HTTP signup -> login -> me chain end to end to prove there is one
    authoritative implementation.

The app's lifespan is intentionally NOT run (TestClient is used without its
context manager, matching test_ml_inference_integration.py), so no real
model weights, OCR, Whisper, or LLM are loaded. init_database() is called
directly instead, against a temp-file DB_PATH, to reproduce exactly the
"schema already created before any router runs" ordering a real deployment
has, without needing the full heavyweight lifespan.

Run from the backend directory:
    pytest tests/test_auth_integration.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# llama_cpp's native library may be absent (it's not a hard test dependency).
# Stub it before importing main so `from slow_lane import SlowLaneBrain` works.
if "llama_cpp" not in sys.modules:
    sys.modules["llama_cpp"] = MagicMock()

import auth_shared  # noqa: E402
import main  # noqa: E402  (import after the llama_cpp guard above)


@pytest.fixture
def real_app_client(tmp_path, monkeypatch):
    """The actual main.app, mounted routers included, pointed at a fresh
    temp database that has already been through the real init_database()
    -- reproducing what a real deployment's startup does before the first
    request ever reaches any router."""
    db_path = tmp_path / "helpers_integration_test.db"
    monkeypatch.setattr(auth_shared, "DB_PATH", db_path)
    auth_shared.init_database()  # what the real lifespan does at startup
    yield TestClient(main.app)  # no context manager -> lifespan is not run
    auth_shared.helper_tokens.clear()


class TestNoDuplicateRouteRegistrations:
    def test_each_auth_and_helpers_path_has_exactly_one_handler(self):
        # The exact defect this class of bug was: two routers separately
        # registering the same method+path, with whichever was included
        # first silently winning at request time. Assert directly against
        # the real app's route table that this can't happen again for any
        # of the auth-adjacent paths.
        path_method_pairs = [
            (route.path, method)
            for route in main.app.routes
            for method in getattr(route, "methods", None) or []
            if getattr(route, "path", "").startswith(("/auth/", "/helpers/"))
        ]
        counts = Counter(path_method_pairs)
        duplicates = {pair: count for pair, count in counts.items() if count > 1}
        assert duplicates == {}


class TestAuthAgainstRealAppAndCanonicalSchema:
    def test_signup_does_not_conflict_with_the_pre_existing_canonical_schema(self, real_app_client, tmp_path):
        # The exact scenario the review flagged: helpers.db already has the
        # canonical schema (created by init_database(), as real startup
        # does) before routers/auth.py ever touches it.
        response = real_app_client.post(
            "/auth/signup",
            json={"email": "integration@example.com", "password": "hunter2222"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        # And it wrote into that same real database file -- not a second,
        # divergent one -- using the canonical column names.
        db_path = auth_shared.DB_PATH
        assert db_path == tmp_path / "helpers_integration_test.db"
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT name, email, password_hash FROM helpers WHERE email=?",
            ("integration@example.com",),
        ).fetchone()
        assert row is not None
        assert row[1] == "integration@example.com"

    def test_login_token_is_accepted_by_the_real_helpers_me_route(self, real_app_client):
        # There must be one coherent token source: a token from /auth/login
        # must validate against the real, live GET /helpers/me route (not
        # routers/auth.py's own store), since both now read the same
        # auth_shared.helper_tokens dict. This is a real HTTP request
        # through the actual app, not a direct function call.
        real_app_client.post(
            "/auth/signup",
            json={"email": "cross-validate@example.com", "password": "hunter2222", "name": "Cross Validate"},
        )
        login_response = real_app_client.post(
            "/auth/login",
            json={"email": "cross-validate@example.com", "password": "hunter2222"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        me_response = real_app_client.get("/helpers/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "cross-validate@example.com"

    def test_unrecognized_token_is_rejected(self, real_app_client):
        response = real_app_client.get("/helpers/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert response.status_code == 401


class TestHelpersSignupLoginMeAgainstRealApp:
    """The real HTTP /helpers/signup -> /helpers/login -> /helpers/me chain.

    Exercises main.py's own canonical /helpers/* implementation end to end,
    now that the legacy routers/helpers.py registration that used to
    silently shadow it has been removed.
    """

    def test_full_signup_login_me_chain(self, real_app_client):
        signup_response = real_app_client.post(
            "/helpers/signup",
            json={
                "name": "Real Helper",
                "email": "real-helper@example.com",
                "password": "hunter2222",
                "age": 30,
                "phone": "555-0100",
                "address": "1 Example St",
                "emergency_contact_name": "Emergency Person",
                "emergency_contact_phone": "555-0199",
                "experience_level": "beginner",
            },
        )
        assert signup_response.status_code == 200

        login_response = real_app_client.post(
            "/helpers/login",
            json={"email": "real-helper@example.com", "password": "hunter2222"},
        )
        assert login_response.status_code == 200
        login_body = login_response.json()
        token = login_body["token"]

        # The login response's "helper" object must carry the full profile
        # -- the frontend stores this whole object and reads age/phone/
        # address/emergency_contact_*/experience_level from it later,
        # regardless of which endpoint most recently supplied it.
        helper = login_body["helper"]
        assert helper["name"] == "Real Helper"
        assert helper["email"] == "real-helper@example.com"
        assert helper["age"] == 30
        assert helper["phone"] == "555-0100"
        assert helper["address"] == "1 Example St"
        assert helper["emergency_contact_name"] == "Emergency Person"
        assert helper["emergency_contact_phone"] == "555-0199"
        assert helper["experience_level"] == "beginner"

        me_response = real_app_client.get("/helpers/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        me_body = me_response.json()
        assert me_body["email"] == "real-helper@example.com"
        assert me_body["age"] == 30
        assert me_body["address"] == "1 Example St"

    def test_signup_requires_name_email_and_password(self, real_app_client):
        response = real_app_client.post(
            "/helpers/signup",
            json={"email": "incomplete@example.com", "password": "hunter2222"},
        )
        assert response.status_code == 400

    def test_wrong_password_is_rejected(self, real_app_client):
        real_app_client.post(
            "/helpers/signup",
            json={"name": "Someone", "email": "wrong-pw@example.com", "password": "correct-password"},
        )
        response = real_app_client.post(
            "/helpers/login",
            json={"email": "wrong-pw@example.com", "password": "incorrect-password"},
        )
        assert response.status_code == 401

    def test_passwords_are_not_stored_in_plaintext(self, real_app_client):
        # The defect in the removed legacy implementation: it stored
        # payload.password verbatim. Assert the real database never does.
        real_app_client.post(
            "/helpers/signup",
            json={"name": "Someone", "email": "plaintext-check@example.com", "password": "hunter2222"},
        )
        conn = sqlite3.connect(auth_shared.DB_PATH)
        row = conn.execute(
            "SELECT password_hash FROM helpers WHERE email=?", ("plaintext-check@example.com",)
        ).fetchone()
        assert row[0] != "hunter2222"
