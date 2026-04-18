import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(prefix = "/helpers", tags = ["helpers"])

# In-memory storage (temporary, will reset when server restarts)
helpers_store = {}
helper_sessions = {}


# Request model for helper signup
class HelperSignupRequest(BaseModel):
    name: str
    age: Optional[int] = None
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    experience_level: Optional[str] = None
    password: str


# Request model for helper login
class HelperLoginRequest(BaseModel):
    email: EmailStr
    password: str


# Create new helper account
@router.post("/signup", status_code=201)
async def helper_signup(payload: HelperSignupRequest):
    email = payload.email.lower().strip()

    # Check duplicate email
    if email in helpers_store:
        raise HTTPException(status_code = 409, detail = "Helper account already exists")

    helper_id = str(uuid.uuid4())

    # Store helper data
    helper_record = {
        "id": helper_id,
        "name": payload.name,
        "age": payload.age,
        "email": email,
        "phone": payload.phone,
        "address": payload.address,
        "emergency_contact_name": payload.emergency_contact_name,
        "emergency_contact_phone": payload.emergency_contact_phone,
        "experience_level": payload.experience_level,
        "password": payload.password,
    }

    helpers_store[email] = helper_record

    return {
        "message": "Helper account created successfully",
        "helper_id": helper_id,
    }


# Authenticate helper and return session token
@router.post("/login")
async def helper_login(payload: HelperLoginRequest):
    email = payload.email.lower().strip()
    helper = helpers_store.get(email)

    # Validate credentials
    if not helper or helper["password"] != payload.password:
        raise HTTPException(status_code = 401, detail = "Invalid credentials")

    token = str(uuid.uuid4())
    helper_sessions[token] = helper["id"]

    return {
        "token": token,
        "helper": {
            "id": helper["id"],
            "name": helper["name"],
            "age": helper["age"],
            "email": helper["email"],
            "phone": helper["phone"],
            "address": helper["address"],
            "emergency_contact_name": helper["emergency_contact_name"],
            "emergency_contact_phone": helper["emergency_contact_phone"],
            "experience_level": helper["experience_level"],
        },
    }

# Delete helper account by id
@router.delete("/{helper_id}", status_code = 204)
async def delete_helper(helper_id: str, token: str):
    # Validate session token
    if token not in helper_sessions:
        raise HTTPException(status_code = 401, detail="Unauthorized")

    # Find helper by id
    helper_email = None
    for email, helper in helpers_store.items():
        if helper["id"] == helper_id:
            helper_email = email
            break

    # Helper not found
    if not helper_email:
        raise HTTPException(status_code = 404, detail="Helper not found")

    # Remove helper record
    del helpers_store[helper_email]

    # Remove related sessions
    tokens_to_delete = []
    for session_token, session_helper_id in helper_sessions.items():
        if session_helper_id == helper_id:
            tokens_to_delete.append(session_token)

    for session_token in tokens_to_delete:
        del helper_sessions[session_token]

    return