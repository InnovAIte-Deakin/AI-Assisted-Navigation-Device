"""Real-app integration tests for /auth/* against the actual database initialization.

Unlike test_auth.py (which calls auth.signup()/auth.login() as plain Python
functions against an isolated temp database), these tests import the actual
`main.app` -- with routers/auth.py mounted exactly as production does -- and
reproduce the specific integration concern raised in review of this PR:

  * The real backend startup runs main.py's init_database(), which creates
    helpers.db with the canonical schema (name/email/password_hash/...)
    *before* any request is served. routers/auth.py must not fail against
    that already-created table, and must not create a second, divergent
    database file.
  * A token issued by POST /auth/login must validate against the existing
    GET /helpers/me path -- there must be one coherent token store, not
    two incompatible auth systems.

The app's lifespan is intentionally NOT run (TestClient is used without its
context manager, matching test_ml_inference_integration.py), so no real
model weights, OCR, Whisper, or LLM are loaded. init_database() is called
directly instead, against a temp-file DB_PATH, to reproduce exactly the
"schema already created before routers/auth.py runs" ordering a real
deployment has, without needing the full heavyweight lifespan.

Run from the backend directory:
    pytest tests/test_auth_integration.py -v
"""

from __future__ import annotations

import sqlite3
import sys
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
    request ever reaches routers/auth.py."""
    db_path = tmp_path / "helpers_integration_test.db"
    monkeypatch.setattr(auth_shared, "DB_PATH", db_path)
    auth_shared.init_database()  # what the real lifespan does at startup
    yield TestClient(main.app)  # no context manager -> lifespan is not run
    auth_shared.helper_tokens.clear()


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

    def test_login_token_is_accepted_by_the_existing_helpers_me_handler(self, real_app_client):
        # There must be one coherent token source: a token from /auth/login
        # must validate against /helpers/me's real handler (not
        # routers/auth.py's own store), since both now read the same
        # auth_shared.helper_tokens dict.
        #
        # This calls main._get_helper_by_token() -- the exact function
        # /helpers/me delegates to -- directly, rather than through
        # real_app_client.get("/helpers/me", ...). A real HTTP GET to any
        # path that partially overlaps an include_router() mount prefix
        # without matching one of that router's own routes (e.g.
        # "/helpers/me" against routers/helpers.py's "/helpers" mount, which
        # only defines /signup, /login, and /{helper_id}) crashes inside
        # opentelemetry-instrumentation-fastapi's route-name resolver on the
        # fastapi/starlette versions installed in this dev environment
        # (AttributeError: '_IncludedRouter' object has no attribute
        # 'path') -- the exact same pre-existing, environment-specific
        # limitation already documented for test_ml_inference_integration.py
        # in this test suite, unrelated to this PR's auth changes. Calling
        # the real function directly still exercises the real main module,
        # the real database this fixture initialized, and the real shared
        # token store -- it only sidesteps the unrelated instrumentation bug
        # in the HTTP layer.
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

        helper = main._get_helper_by_token(token)
        assert helper["email"] == "cross-validate@example.com"

    def test_unrecognized_token_is_rejected(self, real_app_client):
        with pytest.raises(Exception) as exc_info:
            main._get_helper_by_token("not-a-real-token")
        assert getattr(exc_info.value, "status_code", None) == 401
