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
                    "region": data.get("regionName"),
                    "source": "server_ip"
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
                    "region": addr.get("state"),
                    "country": addr.get("country"),
                }
    except Exception as e:
        print(f"Error in full reverse geocoding: {e}")
        raise
    return {"city": None, "region": None, "country": None}

async def get_browser_location(
    context: Context,
    timeout: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    Get user location from browser via WebSocket.

    Args:
        context: FastMCP context containing session information
        timeout: Timeout in seconds for waiting for browser response

    Returns:
        Dict containing raw location data with geocoding info or None if unavailable
    """
    try:
        import threading
        current_loop = asyncio.get_event_loop()
        current_thread = threading.current_thread()
        print(f"[LOCATION] get_browser_location running in thread: {current_thread.name}, event loop: {id(current_loop)}", flush=True)
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
        
        try:
            result = await connection_manager.send_json(session_id, {
                "type": "LOCATION_REQUEST",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "accuracy_level": "high"
            })

            if not result:
                return None

            # Poll cache for response
            from backend.infrastructure.websocket.message_cache import get_message_cache
            cache = get_message_cache()
            for _ in range(int(timeout * 10)): 
                location_data = cache.get_message("location", session_id)
                if location_data:
                    return location_data

                await asyncio.sleep(0.1)

            print(f"[LOCATION] Timeout after {timeout}s, no response received", flush=True)
            return None

        except Exception as e:
            print(f"Error getting browser location: {e}")
            return None

    except Exception as e:
        print(f"Error in get_browser_location: {e}")
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
            browser_data = await get_browser_location(context, timeout=wait_time)
            if not browser_data:
                print(f"[LOCATION] Browser location unavailable, falling back to server IP")

        # Fallback to server IP geolocation if browser location failed
        if not browser_data:
            server_data = await _fetch_server_location()

        # Unified LocationData assembly with geocoding
        if browser_data:
            # Browser data: get geocoding info
            geocode_data = await _reverse_geocode(
                browser_data["latitude"],
                browser_data["longitude"]
            )

            from backend.infrastructure.mcp.location_manager import LocationData
            return LocationData(
                latitude=browser_data["latitude"],
                longitude=browser_data["longitude"],
                accuracy=browser_data.get("accuracy"),
                source="browser_geolocation",
                session_id=context.client_id,
                city=geocode_data.get("city"),
                region=geocode_data.get("region"),
                country=geocode_data.get("country")
            )

        elif server_data:
            # Server data: already has basic geocoding info
            from backend.infrastructure.mcp.location_manager import LocationData
            return LocationData(
                latitude=server_data["latitude"],
                longitude=server_data["longitude"],
                source="server_ip_geolocation",
                session_id=context.client_id,
                city=server_data.get("city"),
                region=server_data.get("region"),
                country=server_data.get("country")
            )

    except Exception as e:
        print(f"Error in get_user_location: {e}")
        raise

    return None
