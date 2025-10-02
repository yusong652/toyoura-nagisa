"""
Location Response Manager

Manages real-time location responses from browser using asyncio Events.
Replaces polling-based message cache with efficient event-driven approach.
"""
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LocationResponse:
    """Location response data from browser"""
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    accuracy: Optional[str] = None
    error: Optional[str] = None


class LocationResponseManager:
    """
    Manages location responses using asyncio Events for real-time updates.

    Each session has an Event that gets set when location response arrives.
    Waiting code can efficiently await the Event instead of polling cache.
    """

    def __init__(self):
        # Map session_id -> (Event, LocationResponse)
        self._pending_requests: Dict[str, tuple[asyncio.Event, Optional[LocationResponse]]] = {}

    def create_request(self, session_id: str) -> asyncio.Event:
        """
        Create a new location request for session.

        Args:
            session_id: Session identifier

        Returns:
            Event that will be set when response arrives
        """
        event = asyncio.Event()
        self._pending_requests[session_id] = (event, None)
        return event

    def set_response(self, session_id: str, location_data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """
        Set location response for session and notify waiting code.

        Args:
            session_id: Session identifier
            location_data: Location data from browser
            error: Error message if location request failed
        """
        if session_id not in self._pending_requests:
            # No pending request for this session, ignore
            return

        event, _ = self._pending_requests[session_id]

        # Create response object
        if location_data:
            response = LocationResponse(
                latitude=location_data.get("latitude", 0.0),
                longitude=location_data.get("longitude", 0.0),
                city=location_data.get("city"),
                country=location_data.get("country"),
                accuracy=location_data.get("accuracy")
            )
        else:
            response = LocationResponse(
                latitude=0.0,
                longitude=0.0,
                error=error or "Unknown error"
            )

        # Update pending request with response
        self._pending_requests[session_id] = (event, response)

        # Notify waiting code
        event.set()

    def get_response(self, session_id: str) -> Optional[LocationResponse]:
        """
        Get location response for session (non-blocking).

        Args:
            session_id: Session identifier

        Returns:
            LocationResponse if available, None otherwise
        """
        if session_id in self._pending_requests:
            _, response = self._pending_requests[session_id]
            return response
        return None

    def cleanup_request(self, session_id: str):
        """
        Clean up location request for session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._pending_requests:
            del self._pending_requests[session_id]


# Global instance
_location_response_manager: Optional[LocationResponseManager] = None


def get_location_response_manager() -> LocationResponseManager:
    """Get global location response manager instance"""
    global _location_response_manager
    if _location_response_manager is None:
        _location_response_manager = LocationResponseManager()
    return _location_response_manager
