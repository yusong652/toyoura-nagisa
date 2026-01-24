import uuid
from datetime import datetime
from typing import Any, List, Dict, Optional, TypedDict

# Memory manager initialization removed - preparing for memory system refactoring
# memory_manager = MemoryManager()


class _MessageParseResultRequired(TypedDict):
    """Required fields in message parsing result"""

    content: List[Dict[str, Any]]
    session_id: str
    message: str
    request_id: str
    enable_memory: bool


class MessageParseResult(_MessageParseResultRequired, total=False):
    """Type definition for message parsing result with optional fields"""

    timestamp: Optional[int]
    id: Optional[str]
    mentioned_files: List[str]  # File paths from @ mentions


def parse_message_data(data: dict) -> MessageParseResult:
    """Parse WebSocket message data in unified format"""
    session_id = data.get("session_id", "default_session")
    text = data.get("message", "")
    files = data.get("files", [])
    msg_id = data.get("message_id")
    enable_memory = data.get("enable_memory", True)  # Default to True, simplified
    mentioned_files = data.get("mentioned_files", [])  # File mentions from frontend

    # Convert ISO timestamp to milliseconds if present
    timestamp = None
    if data.get("timestamp"):
        try:
            dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1000)
        except:
            timestamp = None

    # Build content array - use standard ContentBlock format
    content = []
    if text:
        content.append({"type": "text", "text": text})

    for file in files:
        if file["type"].startswith("image/"):
            b64_data = file["data"]
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            content.append({"inline_data": {"mime_type": file["type"], "data": b64_data}})

    result: MessageParseResult = {
        "content": content,
        "timestamp": timestamp,
        "id": msg_id,
        "session_id": session_id,
        "message": text,  # Add text message for streaming handler
        "request_id": str(uuid.uuid4()),  # Generate unique request ID
        "enable_memory": enable_memory,  # Add memory setting
    }

    # Add mentioned_files only if non-empty (optional field)
    if mentioned_files:
        result["mentioned_files"] = mentioned_files

    return result
