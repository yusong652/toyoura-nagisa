"""
Location Response Manager

Manages real-time location responses from browser using asyncio Futures.
Unified with bash confirmation pattern for consistent async waiting behavior.
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
    Manages location responses using asyncio Futures for real-time updates.

    Each session has a Future that gets resolved when location response arrives.
    This pattern matches the bash confirmation service for consistency.
    """

    def __init__(self):
        # Map session_id -> Future[LocationResponse]
        self._pending_requests: Dict[str, asyncio.Future[LocationResponse]] = {}

    def create_request(self, session_id: str) -> asyncio.Future[LocationResponse]:
        """
        Create a new location request for session.

        Args:
            session_id: Session identifier

        Returns:
            Future[LocationResponse]: Future that will be resolved when response arrives
        """
        future: asyncio.Future[LocationResponse] = asyncio.Future()
        self._pending_requests[session_id] = future
        return future

    def set_response(self, session_id: str, location_data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """
        Set location response for session and resolve the waiting Future.

        Args:
            session_id: Session identifier
            location_data: Location data from browser
            error: Error message if location request failed
        """
        if session_id not in self._pending_requests:
            # No pending request for this session, ignore
            return

        future = self._pending_requests[session_id]

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

        # Resolve the Future with response
        if not future.done():
            future.set_result(response)

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
