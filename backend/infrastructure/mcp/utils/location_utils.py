"""
Location Utilities - Shared location detection and geocoding functions
"""

import asyncio
import requests
from typing import Optional, Dict, Any, TYPE_CHECKING
from fastmcp.server.context import Context  # type: ignore

if TYPE_CHECKING:
    from backend.infrastructure.mcp.location_manager import LocationData

def _fetch_server_location() -> Optional[Dict[str, Any]]:
    """Fallback: geolocate server IP via ip-api.com"""
    try:
        resp = requests.get("http://ip-api.com/json", timeout=5)
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
    except Exception:
        pass
    return None

def _reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Use OpenStreetMap Nominatim to reverse-geocode coordinates to city name"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "json", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1}
        headers = {"User-Agent": "Nagisa-FastMCP/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            return addr.get("city") or addr.get("town") or addr.get("village")
    except Exception:
        pass
    return None


def _reverse_geocode_full(lat: float, lon: float) -> Dict[str, Optional[str]]:
    """Use OpenStreetMap Nominatim to reverse-geocode coordinates to full address"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "json", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1}
        headers = {"User-Agent": "Nagisa-FastMCP/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            return {
                "city": addr.get("city") or addr.get("town") or addr.get("village"),
                "region": addr.get("state"),
                "country": addr.get("country"),
            }
    except Exception:
        pass
    return {"city": None, "region": None, "country": None}

async def get_browser_location(
    context: Context,
    timeout: float = 5.0
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
        session_id = context.client_id
        if not session_id:
            return None

        # Get app and connection manager
        app = getattr(getattr(context, "fastmcp", None), "app", None)
        if not app or not hasattr(app.state, "connection_manager"):
            return None

        # Import location response events storage
        from backend.presentation.websocket.router import _location_response_events
        location_events = _location_response_events
        
        # Check if WebSocket connection exists
        cm = app.state.connection_manager
        if session_id not in cm.connections:
            return None
        
        # Create event for this location request
        location_event = asyncio.Event()
        location_events[session_id] = {
            "event": location_event,
            "location_data": None,
            "success": False,
            "timestamp": None
        }
        
        try:
            # Send location request via WebSocket
            await cm.send_json(session_id, {"type": "REQUEST_LOCATION"})
            
            # Wait for response with timeout
            await asyncio.wait_for(location_event.wait(), timeout=timeout)
            
            # Get the response data
            event_info = location_events.get(session_id, {})
            if event_info.get("success") and event_info.get("location_data"):
                location_data = event_info["location_data"]
                
                # Get city/region/country via reverse geocoding
                geocode_data = _reverse_geocode_full(
                    location_data["latitude"],
                    location_data["longitude"]
                )
                
                # Import here to avoid circular imports
                from backend.infrastructure.mcp.location_manager import LocationData
                
                return LocationData(
                    latitude=location_data["latitude"],
                    longitude=location_data["longitude"],
                    accuracy=location_data.get("accuracy"),
                    source="browser_geolocation",
                    session_id=session_id,
                    timestamp=event_info.get("timestamp", int(asyncio.get_event_loop().time())),
                    city=geocode_data.get("city"),
                    region=geocode_data.get("region"),
                    country=geocode_data.get("country")
                )
        except asyncio.TimeoutError:
            pass
        finally:
            # Clean up the event
            location_events.pop(session_id, None)
            
    except Exception:
        pass
    
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
        
        # Fallback to server IP geolocation
        server_data = _fetch_server_location()
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

    except Exception:
        pass
    
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
        return _reverse_geocode(
            location_data.latitude, 
            location_data.longitude
        )
    
    return None 