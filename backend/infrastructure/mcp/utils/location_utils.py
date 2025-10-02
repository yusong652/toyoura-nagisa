"""
Location Utilities - Shared location detection and geocoding functions
"""

import asyncio
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from fastmcp.server.context import Context  # type: ignore

if TYPE_CHECKING:
    from backend.infrastructure.mcp.location_manager import LocationData

async def _fetch_server_location() -> Optional[Dict[str, Any]]:
    """Fallback: geolocate server IP via ip-api.com"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://ip-api.com/json")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "success":
                return {
                    "latitude": data["lat"],
                    "longitude": data["lon"],
                    "city": data.get("city"),
                    "country": data.get("country"),
                    "accuracy": "low"
                }
    except Exception as e:
        print(f"Error fetching server location: {e}")
        raise
    return None


async def _reverse_geocode(lat: float, lon: float) -> Dict[str, Optional[str]]:
    """Use OpenStreetMap Nominatim to reverse-geocode coordinates to full address"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "json", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1}
        headers = {"User-Agent": "Nagisa-FastMCP/1.0"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                addr = resp.json().get("address", {})
                return {
                    "city": addr.get("city") or addr.get("town") or addr.get("village"),
                    "country": addr.get("country"),
                }
    except Exception as e:
        print(f"Error in full reverse geocoding: {e}")
        raise
    return {"city": None, "country": None}

async def _fetch_browser_location(
    context: Context,
    timeout: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    Fetch user location from browser via WebSocket using asyncio Event.

    Args:
        context: FastMCP context containing session information
        timeout: Timeout in seconds for waiting for browser response

    Returns:
        Dict containing location data with consistent structure or None if unavailable
    """
    try:
        session_id = context.client_id
        if not session_id:
            return None

        # Get FastAPI app from MCP context
        try:
            app = context.fastmcp.app # type: ignore
            websocket_handler = app.state.websocket_handler
            connection_manager = websocket_handler.get_connection_manager()
        except AttributeError:
            return None

        # Create location request and get event
        from backend.infrastructure.websocket.location_response_manager import get_location_response_manager
        manager = get_location_response_manager()
        event = manager.create_request(session_id)

        try:
            # Send location request to browser
            result = await connection_manager.send_json(session_id, {
                "type": "LOCATION_REQUEST",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "accuracy_level": "high"
            })

            if not result:
                manager.cleanup_request(session_id)
                return None

            # Wait for response with timeout
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"[LOCATION] Browser location request timed out after {timeout}s")
                manager.cleanup_request(session_id)
                return None

            # Get response from manager
            response = manager.get_response(session_id)
            manager.cleanup_request(session_id)

            if response and not response.error:
                # Return standardized location data structure
                return {
                    "latitude": response.latitude,
                    "longitude": response.longitude,
                    "city": response.city,
                    "country": response.country,
                    "accuracy": response.accuracy
                }
            else:
                print(f"[LOCATION] Browser location error: {response.error if response else 'No response'}")
                return None

        except Exception as e:
            print(f"Error getting browser location: {e}")
            manager.cleanup_request(session_id)
            return None

    except Exception as e:
        print(f"Error in _fetch_browser_location: {e}")
        return None


async def get_user_location(
    context: Context,
    wait_time: int = 10,
    prefer_browser: bool = True
) -> Optional['LocationData']:
    """
    Get user location with browser priority.

    Args:
        context: FastMCP context containing session information
        wait_time: Timeout for browser location (defaults to 10 seconds)
        prefer_browser: If True, try browser location first (default True)

    Returns:
        LocationData object with location data or None if unavailable
    """
    try:
        browser_data = None
        server_data = None

        # Try browser location first if preferred
        if prefer_browser:
            browser_data = await _fetch_browser_location(context, timeout=wait_time)
            if not browser_data:
                print(f"[LOCATION] Browser location unavailable, falling back to server IP")

        # Fallback to server IP geolocation if browser location failed
        if not browser_data:
            server_data = await _fetch_server_location()

        # Unified LocationData assembly with geocoding
        location_data = browser_data or server_data
        if location_data:
            # Get additional geocoding info if needed (for browser data without city)
            if browser_data and not location_data.get("city"):
                geocode_data = await _reverse_geocode(
                    location_data["latitude"],
                    location_data["longitude"]
                )
                # Use geocoded data if original data lacks location info
                city = geocode_data.get("city")
                country = geocode_data.get("country")
            else:
                # Use existing location info from the data source
                city = location_data.get("city")
                country = location_data.get("country")

            from backend.infrastructure.mcp.location_manager import LocationData
            return LocationData(
                latitude=location_data["latitude"],
                longitude=location_data["longitude"],
                accuracy=location_data.get("accuracy"),
                session_id=context.client_id,
                city=city,
                country=country
            )

    except Exception as e:
        print(f"Error in get_user_location: {e}")
        raise

    return None
