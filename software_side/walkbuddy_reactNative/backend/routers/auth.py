from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3, hashlib, secrets

router = APIRouter(prefix="/auth")

class AuthBody(BaseModel):
    email: str
    password: str

@router.post("/signup")
def signup(body: AuthBody):
    db = sqlite3.connect("helpers.db")
    db.execute("CREATE TABLE IF NOT EXISTS helpers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw TEXT)")
    try:
        db.execute("INSERT INTO helpers (email, pw) VALUES (?,?)",
                   (body.email, hashlib.sha256(body.password.encode()).hexdigest()))
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    return {"ok": True}

@router.post("/login")
def login(body: AuthBody):
    db = sqlite3.connect("helpers.db")
    row = db.execute("SELECT id FROM helpers WHERE email=? AND pw=?",
                     (body.email, hashlib.sha256(body.password.encode()).hexdigest())).fetchone()
    if not row:
        raise HTTPException(401, "Invalid credentials")
    return {"ok": True, "token": secrets.token_hex(32)}
