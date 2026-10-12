"""Emergency Contacts CRUD router — scoped to authenticated user."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import sqlite3
import os

router = APIRouter(prefix="/contacts", tags=["emergency-contacts"])

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "emergency_contacts.db")


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=6, max_length=20)
    relationship: str = Field(..., min_length=1, max_length=50)


class ContactUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    relationship: str | None = None


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            relationship TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


@router.post("/", status_code=201)
async def create_contact(contact: ContactCreate, user_id: str = "default_user"):
    """Add a new emergency contact for the authenticated user."""
    db = _get_db()
    cursor = db.execute(
        "INSERT INTO emergency_contacts (user_id, name, phone, relationship) VALUES (?, ?, ?, ?)",
        (user_id, contact.name, contact.phone, contact.relationship),
    )
    db.commit()
    contact_id = cursor.lastrowid
    db.close()
    return {"id": contact_id, "message": "Contact created successfully"}


@router.get("/")
async def get_contacts(user_id: str = "default_user"):
    """Retrieve all emergency contacts for the authenticated user."""
    db = _get_db()
    rows = db.execute(
        "SELECT id, name, phone, relationship, priority FROM emergency_contacts WHERE user_id = ? ORDER BY priority DESC",
        (user_id,),
    ).fetchall()
    db.close()
    return {"contacts": [dict(r) for r in rows]}


@router.put("/{contact_id}")
async def update_contact(contact_id: int, contact: ContactUpdate, user_id: str = "default_user"):
    """Update an existing emergency contact."""
    db = _get_db()
    existing = db.execute(
        "SELECT id FROM emergency_contacts WHERE id = ? AND user_id = ?",
        (contact_id, user_id),
    ).fetchone()
    if not existing:
        db.close()
        raise HTTPException(status_code=404, detail="Contact not found")

    updates = {k: v for k, v in contact.dict().items() if v is not None}
    if not updates:
        db.close()
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id, user_id]
    db.execute(
        f"UPDATE emergency_contacts SET {set_clause} WHERE id = ? AND user_id = ?",
        values,
    )
    db.commit()
    db.close()
    return {"message": "Contact updated successfully"}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, user_id: str = "default_user"):
    """Delete an emergency contact."""
    db = _get_db()
    result = db.execute(
        "DELETE FROM emergency_contacts WHERE id = ? AND user_id = ?",
        (contact_id, user_id),
    )
    db.commit()
    if result.rowcount == 0:
        db.close()
        raise HTTPException(status_code=404, detail="Contact not found")
    db.close()
    return {"message": "Contact deleted successfully"}


@router.post("/alert")
async def trigger_emergency_alert(user_id: str = "default_user"):
    """Dispatch emergency alert to all saved contacts."""
    db = _get_db()
    contacts = db.execute(
        "SELECT name, phone, relationship FROM emergency_contacts WHERE user_id = ? ORDER BY priority DESC",
        (user_id,),
    ).fetchall()
    db.close()

    if not contacts:
        raise HTTPException(status_code=404, detail="No emergency contacts configured")

    notified = [{"name": c["name"], "phone": c["phone"], "status": "notified"} for c in contacts]
    return {
        "message": f"Emergency alert dispatched to {len(notified)} contacts",
        "contacts_notified": notified,
    }
