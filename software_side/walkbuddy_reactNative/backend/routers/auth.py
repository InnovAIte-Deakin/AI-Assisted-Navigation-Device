from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3, hashlib, secrets, time

router = APIRouter(prefix="/auth")

# Iteration count in the same order of magnitude as Django's historical
# default PBKDF2 hasher; stdlib-only, no new dependency required.
PBKDF2_ITERATIONS = 260_000


class AuthBody(BaseModel):
    email: str
    password: str


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS).hex()


def _ensure_tables(db):
    # Called from both signup() and login() — previously only signup() did
    # this, so login() crashed with an unhandled OperationalError instead of
    # a clean 401 if called before anyone had ever signed up.
    db.execute(
        "CREATE TABLE IF NOT EXISTS helpers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw TEXT, salt TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS helper_tokens (token TEXT PRIMARY KEY, helper_id INTEGER, created_at REAL)"
    )


@router.post("/signup")
def signup(body: AuthBody):
    db = sqlite3.connect("helpers.db")
    _ensure_tables(db)
    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(body.password, salt)
    try:
        db.execute(
            "INSERT INTO helpers (email, pw, salt) VALUES (?,?,?)",
            (body.email, pw_hash, salt.hex()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    return {"ok": True}


@router.post("/login")
def login(body: AuthBody):
    db = sqlite3.connect("helpers.db")
    _ensure_tables(db)
    row = db.execute(
        "SELECT id, pw, salt FROM helpers WHERE email=?", (body.email,)
    ).fetchone()
    if not row:
        raise HTTPException(401, "Invalid credentials")

    helper_id, stored_hash, salt_hex = row
    if _hash_password(body.password, bytes.fromhex(salt_hex)) != stored_hash:
        raise HTTPException(401, "Invalid credentials")

    # Previously this token was generated and returned but never stored
    # anywhere, so no later request could ever validate it. Now persisted
    # against the helper it belongs to, so a future auth-check can look it up.
    token = secrets.token_hex(32)
    db.execute(
        "INSERT INTO helper_tokens (token, helper_id, created_at) VALUES (?,?,?)",
        (token, helper_id, time.time()),
    )
    db.commit()
    return {"ok": True, "token": token}
