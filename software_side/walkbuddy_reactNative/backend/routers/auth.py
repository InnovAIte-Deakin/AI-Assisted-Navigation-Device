from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import uuid

import auth_shared

router = APIRouter(prefix="/auth")


class AuthBody(BaseModel):
    email: str
    password: str
    # Optional: the canonical helpers table requires a non-null name. When
    # this endpoint's caller doesn't supply one, signup() falls back to the
    # email's local-part rather than rejecting the request, since AuthBody
    # was never a full profile form the way /helpers/signup's payload is.
    name: str | None = None


@router.post("/signup")
def signup(body: AuthBody):
    # Reuses the exact same database file, "helpers" table schema, and
    # password hashing as main.py's /helpers/signup -- previously this
    # router created its own divergent (email/pw/salt) schema in the same
    # helpers.db file, which either silently failed against the real
    # schema (CREATE TABLE IF NOT EXISTS does not migrate an existing
    # table) or wrote to a second, divergent database if the relative path
    # resolved differently.
    auth_shared.init_database()
    name = (body.name or body.email.split("@", 1)[0]).strip() or "helper"
    db = sqlite3.connect(auth_shared.DB_PATH)
    try:
        db.execute(
            "INSERT INTO helpers (name, email, password_hash) VALUES (?,?,?)",
            (name, body.email, auth_shared.hash_password(body.password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    finally:
        db.close()
    return {"ok": True}


@router.post("/login")
def login(body: AuthBody):
    auth_shared.init_database()
    db = sqlite3.connect(auth_shared.DB_PATH)
    try:
        row = db.execute(
            "SELECT id, password_hash FROM helpers WHERE email=?", (body.email,)
        ).fetchone()
    finally:
        db.close()
    if not row:
        raise HTTPException(401, "Invalid credentials")

    helper_id, stored_hash = row
    if not auth_shared.verify_password(body.password, stored_hash):
        raise HTTPException(401, "Invalid credentials")

    # Issued into the same in-memory token store main.py's /helpers/me and
    # /helpers/delete-account read from -- previously this router persisted
    # tokens into a second, separate SQLite table nothing else ever
    # checked, so a token from here could never validate anywhere else.
    token = str(uuid.uuid4())
    auth_shared.helper_tokens[token] = helper_id
    return {"ok": True, "token": token}
