"""
WebSocket Message Cache Service

Simple cache for WebSocket message responses.
"""
from typing import Dict, Any, Optional


class WebSocketMessageCache:
    """Simple WebSocket message cache"""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def store_message(self, message_type: str, session_id: str, data: Any):
        """Store message in cache"""
        key = f"{message_type}_{session_id}"
        self._cache[key] = data

    def get_message(self, message_type: str, session_id: str) -> Optional[Any]:
        """Get and remove message from cache"""
        key = f"{message_type}_{session_id}"
        return self._cache.pop(key, None)

    def cleanup_session(self, session_id: str):
        """Clean up all messages for a session"""
        keys_to_remove = [k for k in self._cache.keys() if session_id in k]
        for key in keys_to_remove:
            del self._cache[key]


# Global instance
_message_cache: Optional[WebSocketMessageCache] = None


def get_message_cache() -> WebSocketMessageCache:
    """Get global message cache instance"""
    global _message_cache
    if _message_cache is None:
        _message_cache = WebSocketMessageCache()
    return _message_cache