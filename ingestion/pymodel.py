from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class Sender(BaseModel):
    """Represents the sender of a message"""
    id: str
    display_name: str
    username: Optional[str] = None


class MediaItem(BaseModel):
    """Represents a media item (photo, audio, or video)"""
    type: Literal["photo", "audio", "video", "document"]
    file_id: str
    mime_type: Optional[str] = None
    caption: Optional[str] = None


class Content(BaseModel):
    """Normalized content of a message"""
    text: Optional[str] = None
    media_items: Optional[List[MediaItem]] = None
    reply_to_id: Optional[str] = None
    forwarded_from: Optional[str] = None


class CanonicalEvent(BaseModel):
    """Canonical event structure for cross-platform messaging"""
    event_id: str
    platform: Literal["telegram", "slack", "whatsapp"]
    received_at: datetime
    sender: Sender
    event_type: str  # "text_message" | "media" | "reaction" | "join" | "poll" | "system_alert"
    description: str
    content: Content
