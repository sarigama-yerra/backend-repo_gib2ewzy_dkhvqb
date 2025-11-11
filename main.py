import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

from database import create_document, get_documents, db

app = FastAPI(title="Chat App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Utilities
# -----------------------------

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    if doc.get("_id"):
        doc["id"] = str(doc.pop("_id"))
    # Convert nested ObjectIds if any
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


def serialize_list(docs: List[dict]):
    return [serialize_doc(d) for d in docs]


# -----------------------------
# Root & Health
# -----------------------------

@app.get("/")
def read_root():
    return {"message": "Chat API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -----------------------------
# Schemas (Requests)
# -----------------------------

class CreateUser(BaseModel):
    display_name: str
    avatar_url: Optional[str] = None


class CreateRoom(BaseModel):
    name: str
    is_private: bool = False
    members: Optional[List[str]] = None


class JoinRoom(BaseModel):
    user_id: str


class SendMessage(BaseModel):
    sender_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    type: str = "text"


# -----------------------------
# Users
# -----------------------------

@app.post("/api/users")
def create_user(payload: CreateUser):
    user = {
        "display_name": payload.display_name,
        "avatar_url": payload.avatar_url,
        "status": "online",
    }
    user_id = create_document("user", user)
    return {"id": user_id, **user}


@app.get("/api/users")
def list_users():
    users = get_documents("user", {})
    return serialize_list(users)


@app.get("/api/users/{user_id}")
def get_user(user_id: str):
    try:
        docs = get_documents("user", {"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    if not docs:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(docs[0])


# -----------------------------
# Rooms
# -----------------------------

@app.get("/api/rooms")
def list_rooms():
    rooms = get_documents("room", {})
    return serialize_list(rooms)


@app.post("/api/rooms")
def create_room(payload: CreateRoom):
    room = {
        "name": payload.name,
        "type": "channel",
        "members": payload.members or [],
        "is_private": payload.is_private,
    }
    room_id = create_document("room", room)
    return {"id": room_id, **room}


@app.post("/api/rooms/{room_id}/join")
def join_room(room_id: str, payload: JoinRoom):
    # Use direct update via db since helper lacks update
    try:
        oid = ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room id")

    # Ensure user exists
    try:
        user_oid = ObjectId(payload.user_id)
        user = db.user.find_one({"_id": user_oid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    db.room.update_one({"_id": oid}, {"$addToSet": {"members": payload.user_id}})
    doc = db.room.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Room not found")
    return serialize_doc(doc)


# -----------------------------
# Messages
# -----------------------------

@app.get("/api/rooms/{room_id}/messages")
def get_messages(room_id: str, limit: int = 50):
    try:
        ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room id")
    msgs = get_documents("message", {"room_id": room_id}, limit=limit)
    # Sort by created_at if present
    msgs.sort(key=lambda m: m.get("created_at", 0))
    return serialize_list(msgs)


@app.post("/api/rooms/{room_id}/messages")
def send_message(room_id: str, payload: SendMessage):
    # Validate room and user exist
    try:
        room = db.room.find_one({"_id": ObjectId(room_id)})
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room id")

    try:
        user = db.user.find_one({"_id": ObjectId(payload.sender_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    msg = {
        "room_id": room_id,
        "sender_id": payload.sender_id,
        "content": payload.content.strip(),
        "type": payload.type,
        "is_edited": False,
        "is_deleted": False,
    }
    msg_id = create_document("message", msg)
    return {"id": msg_id, **msg}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
