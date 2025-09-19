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

async def _reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Use OpenStreetMap Nominatim to reverse-geocode coordinates to city name"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "json", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1}
        headers = {"User-Agent": "Nagisa-FastMCP/1.0"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                addr = resp.json().get("address", {})
                return addr.get("city") or addr.get("town") or addr.get("village")
    except Exception as e:
        print(f"Error in reverse geocoding: {e}")
        raise
    return None

async def _reverse_geocode_full(lat: float, lon: float) -> Dict[str, Optional[str]]:
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
) -> Optional['LocationData']:
    """
    Get user location from browser via WebSocket.

    Args:
        context: FastMCP context containing session information
        timeout: Timeout in seconds for waiting for browser response

    Returns:
        LocationData object with browser location data or None if unavailable
    """
    try:
        import threading
        current_loop = asyncio.get_event_loop()
        current_thread = threading.current_thread()
        print(f"[LOCATION] get_browser_location running in thread: {current_thread.name}, event loop: {id(current_loop)}", flush=True)
        session_id = context.client_id
        if not session_id:
            return None

        # Get app and websocket handler
        app = getattr(getattr(context, "fastmcp", None), "app", None)
        if not app or not hasattr(app.state, "websocket_handler"):
            return None

        # Get WebSocket handler and location handler
        websocket_handler = getattr(app.state, 'websocket_handler', None)
        if not websocket_handler:
            return None
            
        # Get location handler from message processor
        message_processor = websocket_handler.get_message_processor()
        location_handler = message_processor.location_handler
        
        if not location_handler:
            return None
        
        # Check if WebSocket connection exists
        connection_manager = websocket_handler.get_connection_manager()

        if session_id not in connection_manager.connections:
            return None
        
        try:
            # Send location request directly like heartbeat - no Future needed
            print(f"[LOCATION] Sending location request to session {session_id} (heartbeat-style)", flush=True)

            result = await connection_manager.send_json(session_id, {
                "type": "LOCATION_REQUEST",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "accuracy_level": "high"
            })

            if result:
                print(f"[LOCATION] Successfully sent location request to session {session_id}", flush=True)
            else:
                print(f"[LOCATION] Failed to send location request to session {session_id}", flush=True)
                return None

            # Poll cache for response
            from backend.infrastructure.websocket.message_cache import get_message_cache
            cache = get_message_cache()

            print(f"[LOCATION] Polling cache for response (timeout: {timeout}s)", flush=True)
            for i in range(int(timeout * 10)):  # Poll every 100ms
                location_data = cache.get_message("location", session_id)
                print(f"[LOCATION] Polling attempt {i+1}, got: {location_data}", flush=True)
                if location_data:
                    print(f"[LOCATION] Got cached response after {i * 0.1:.1f}s", flush=True)

                    # Process location data and return LocationData object
                    geocode_data = await _reverse_geocode_full(
                        location_data["latitude"],
                        location_data["longitude"]
                    )

                    from backend.infrastructure.mcp.location_manager import LocationData
                    return LocationData(
                        latitude=location_data["latitude"],
                        longitude=location_data["longitude"],
                        accuracy=location_data.get("accuracy"),
                        source="browser_geolocation",
                        session_id=session_id,
                        city=geocode_data.get("city"),
                        region=geocode_data.get("region"),
                        country=geocode_data.get("country")
                    )

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
        # Try browser location first if preferred
        if prefer_browser:
            browser_loc = await get_browser_location(context, timeout=wait_time)
            if browser_loc:
                return browser_loc
            else:
                print(f"[LOCATION] Browser location unavailable, falling back to server IP")

        # Always fallback to server IP geolocation
        server_data = await _fetch_server_location()
        if server_data:
            # Import here to avoid circular imports
            from backend.infrastructure.mcp.location_manager import LocationData
            return LocationData(
                latitude=server_data["latitude"],
                longitude=server_data["longitude"],
                source="server_ip_geolocation",
                city=server_data.get("city"),
                country=server_data.get("country"),
                region=server_data.get("region"),
                session_id=context.client_id
            )

    except Exception as e:
        print(f"Error in get_user_location: {e}")
        raise

    return None


async def get_user_city(context: Context, wait_time: int = 8) -> Optional[str]:
    """
    Get user's city name using location services.
    
    Args:
        context: FastMCP context containing session information
        wait_time: Timeout for location retrieval (defaults to 8 seconds)
    
    Returns:
        City name string or None if could not be determined
    """
    location_data = await get_user_location(context, wait_time)
    
    if location_data and location_data.city:
        return location_data.city
    elif location_data and location_data.latitude and location_data.longitude:
        # Try reverse geocoding if city not available
        return await _reverse_geocode(
            location_data.latitude,
            location_data.longitude
        )
    
    return None 