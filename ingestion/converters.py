from datetime import datetime
from typing import Optional, List
from telegram import Update, Message
from pymodel import CanonicalEvent, Sender, Content, MediaItem


def telegram_to_canonical(update: Update) -> Optional[CanonicalEvent]:
    """Convert Telegram Update to CanonicalEvent"""
    if not update.message:
        return None
    
    msg: Message = update.message
    
    # Extract sender information (some messages might not have from_user)
    if msg.from_user:
        sender = Sender(
            id=str(msg.from_user.id),
            display_name=msg.from_user.first_name or "Unknown",
            username=msg.from_user.username
        )
    else:
        sender = Sender(
            id="0",
            display_name="System",
            username=None
        )
    
    # Determine event type and build content
    event_type = "text_message"
    description = ""
    media_items: List[MediaItem] = []
    text = None
    
    if msg.text:
        event_type = "text_message"
        description = msg.text
        text = msg.text
    
    elif msg.photo:
        event_type = "media"
        # Placeholder till AI describes it
        description = f"Photo from {sender.display_name} (AI Processing Pending...)"
        photo = msg.photo[-1]  # highest resolution
        media_items.append(MediaItem(
            type="photo",
            file_id=photo.file_id,
            mime_type="image/jpeg",
            caption=msg.caption
        ))
        text = msg.caption
    
    elif msg.video:
        event_type = "media"
        description = f"Video from {sender.display_name}"
        media_items.append(MediaItem(
            type="video",
            file_id=msg.video.file_id,
            mime_type=msg.video.mime_type or "video/mp4",
            caption=msg.caption
        ))
        text = msg.caption
    
    elif msg.audio:
        event_type = "media"
        description = f"Audio from {sender.display_name}"
        media_items.append(MediaItem(
            type="audio",
            file_id=msg.audio.file_id,
            mime_type=msg.audio.mime_type or "audio/mpeg",
            caption=msg.caption
        ))
        text = msg.caption
    
    elif msg.document:
        event_type = "media"
        description = f"Document from {sender.display_name}"
        media_items.append(MediaItem(
            type="document",
            file_id=msg.document.file_id,
            mime_type=msg.document.mime_type,
            caption=msg.caption
        ))
        text = msg.caption
    
    elif msg.new_chat_members:
        event_type = "join"
        members = ", ".join([m.first_name for m in msg.new_chat_members])
        description = f"{members} joined the group"
        text = description
    
    elif msg.left_chat_member:
        event_type = "system_alert"
        description = f"{msg.left_chat_member.first_name} left the group"
        text = description
    
    elif msg.new_chat_title:
        event_type = "system_alert"
        description = f"Group title changed to: {msg.new_chat_title}"
        text = msg.new_chat_title
    
    elif msg.pinned_message:
        event_type = "system_alert"
        description = f"{sender.display_name} pinned a message"
        text = "Message pinned"
    
    else:
        event_type = "system_alert"
        description = f"Other message type from {sender.display_name}"
    
    # Build content
    forwarded_from = None
    if hasattr(msg, 'forward_origin') and msg.forward_origin:
        # Handle different forward origin types
        if hasattr(msg.forward_origin, 'sender_user') and msg.forward_origin.sender_user:
            forwarded_from = msg.forward_origin.sender_user.username or msg.forward_origin.sender_user.first_name
        elif hasattr(msg.forward_origin, 'sender_user_name'):
            forwarded_from = msg.forward_origin.sender_user_name
    
    content = Content(
        text=text,
        media_items=media_items if media_items else None,
        reply_to_id=str(msg.reply_to_message.message_id) if msg.reply_to_message else None,
        forwarded_from=forwarded_from
    )
    
    # Create canonical event
    canonical_event = CanonicalEvent(
        event_id=f"telegram_{msg.message_id}_{msg.chat.id}",
        platform="telegram",
        received_at=msg.date,
        sender=sender,
        event_type=event_type,
        description=description,
        content=content
    )
    
    return canonical_event


def whatsapp_to_canonical(data: dict) -> Optional[CanonicalEvent]:
    """Convert WhatsApp webhook payload to CanonicalEvent"""
    try:
        # Navigate through WhatsApp webhook structure
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        
        # Extract contact and message info
        contacts = value.get('contacts', [{}])[0]
        messages = value.get('messages', [{}])[0]
        
        if not messages:
            return None
        
        # Extract sender information
        sender = Sender(
            id=messages.get('from', ''),
            display_name=contacts.get('profile', {}).get('name', 'Unknown'),
            username=None
        )
        
        # Extract message content
        message_type = messages.get('type', 'text')
        message_id = messages.get('id', '')
        timestamp = int(messages.get('timestamp', 0))
        received_at = datetime.fromtimestamp(timestamp)
        
        # Build content based on message type
        text = None
        media_items = None
        event_type = "text_message"
        description = f"WhatsApp message from {sender.display_name}"
        
        if message_type == 'text':
            text = messages.get('text', {}).get('body', '')
            event_type = "text_message"
            description = f"Text message from {sender.display_name}"
        
        elif message_type == 'image':
            event_type = "media"
            description = f"Image from {sender.display_name}"
            image_data = messages.get('image', {})
            media_items = [MediaItem(
                type="photo",
                file_id=image_data.get('id', ''),
                mime_type=image_data.get('mime_type', 'image/jpeg'),
                caption=image_data.get('caption')
            )]
            text = image_data.get('caption')
        
        elif message_type == 'video':
            event_type = "media"
            description = f"Video from {sender.display_name}"
            video_data = messages.get('video', {})
            media_items = [MediaItem(
                type="video",
                file_id=video_data.get('id', ''),
                mime_type=video_data.get('mime_type', 'video/mp4'),
                caption=video_data.get('caption')
            )]
            text = video_data.get('caption')
        
        elif message_type == 'audio':
            event_type = "media"
            description = f"Audio from {sender.display_name}"
            audio_data = messages.get('audio', {})
            media_items = [MediaItem(
                type="audio",
                file_id=audio_data.get('id', ''),
                mime_type=audio_data.get('mime_type', 'audio/ogg'),
                caption=None
            )]
        
        elif message_type == 'document':
            event_type = "media"
            description = f"Document from {sender.display_name}"
            doc_data = messages.get('document', {})
            media_items = [MediaItem(
                type="document",
                file_id=doc_data.get('id', ''),
                mime_type=doc_data.get('mime_type'),
                caption=doc_data.get('caption')
            )]
            text = doc_data.get('caption')
        
        # Build content
        content = Content(
            text=text,
            media_items=media_items,
            reply_to_id=None,  # WhatsApp doesn't provide this in basic payload
            forwarded_from=None
        )
        
        # Create canonical event
        canonical_event = CanonicalEvent(
            event_id=f"whatsapp_{message_id}",
            platform="whatsapp",
            received_at=received_at,
            sender=sender,
            event_type=event_type,
            description=description,
            content=content
        )
        
        return canonical_event
    
    except Exception as e:
        print(f"Error converting WhatsApp message: {e}")
        return None


def slack_to_canonical(data: dict) -> Optional[CanonicalEvent]:
    """Convert Slack event payload to CanonicalEvent"""
    try:
        # Extract event data
        event = data.get('event', {})
        event_type_raw = event.get('type', '')
        
        # Only process message events
        if event_type_raw != 'message':
            return None
        
        # Skip bot messages to avoid loops
        if event.get('bot_id') or event.get('subtype') == 'bot_message':
            return None
        
        # Extract sender information
        user_id = event.get('user', '')
        # Slack doesn't provide display name in event, using user_id as display name
        # In a real implementation, you'd fetch this from Slack's users.info API
        sender = Sender(
            id=user_id,
            display_name=user_id,  # Could be enhanced with user.info API call
            username=None
        )
        
        # Extract message content
        text = event.get('text', '')
        timestamp = float(event.get('ts', '0'))
        received_at = datetime.fromtimestamp(timestamp)
        
        # Extract additional context
        channel_id = event.get('channel', '')
        channel_type = event.get('channel_type', 'channel')
        event_id = data.get('event_id', '')
        
        # Build content
        content = Content(
            text=text,
            media_items=None,  # Could be enhanced to parse files from event
            reply_to_id=event.get('thread_ts'),  # Thread parent message
            forwarded_from=None
        )
        
        # Create canonical event
        canonical_event = CanonicalEvent(
            event_id=f"slack_{event_id}",
            platform="slack",
            received_at=received_at,
            sender=sender,
            event_type="text_message",
            description=f"Text message from {sender.display_name} in {channel_type}",
            content=content
        )
        
        return canonical_event
    
    except Exception as e:
        print(f"Error converting Slack message: {e}")
        return None
