"""
Database Schemas for Chat App

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class User(BaseModel):
    """Users collection schema -> collection name: "user"""
    display_name: str = Field(..., description="Public display name")
    avatar_url: Optional[str] = Field(None, description="Optional avatar URL")
    status: str = Field("online", description="online, idle, dnd, offline")

class Room(BaseModel):
    """Rooms collection schema -> collection name: "room"""
    name: str = Field(..., description="Room name")
    type: str = Field("channel", description="channel or direct")
    members: List[str] = Field(default_factory=list, description="List of user ids")
    is_private: bool = Field(False, description="Whether room is private")

class Message(BaseModel):
    """Messages collection schema -> collection name: "message"""
    room_id: str = Field(..., description="Room id (string)")
    sender_id: str = Field(..., description="User id (string)")
    content: str = Field(..., description="Message text content")
    type: str = Field("text", description="Message type: text/image/file/system")
    is_edited: bool = Field(False)
    is_deleted: bool = Field(False)
