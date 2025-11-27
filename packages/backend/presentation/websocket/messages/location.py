"""
Location services message schemas.

This module defines WebSocket messages for geolocation functionality,
enabling location requests from backend to frontend and location responses.
"""
from typing import Optional, Dict, Any
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class LocationRequestMessage(BaseWebSocketMessage):
    """
    Location request message schema.

    Sent by backend to request current location from frontend.
    Frontend should respond with LocationResponseMessage containing
    geolocation data or error information.

    Attributes:
        request_id: Unique identifier to match request with response
        accuracy_level: Desired accuracy ("high", "medium", "low")
    """
    type: MessageType = MessageType.LOCATION_REQUEST
    request_id: str
    accuracy_level: str = "high"  # high, medium, low


class LocationResponseMessage(BaseWebSocketMessage):
    """
    Location response message schema.

    Sent by frontend in response to LocationRequestMessage with
    geolocation data or error information.

    Attributes:
        request_id: Matches the request_id from LocationRequestMessage
        location_data: Geolocation data (latitude, longitude, accuracy, etc.)
        error: Error message if location retrieval failed
    """
    type: MessageType = MessageType.LOCATION_RESPONSE
    request_id: Optional[str] = None
    location_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
