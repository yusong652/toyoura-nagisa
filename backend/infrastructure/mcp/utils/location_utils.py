"""
Location Utilities - Shared location detection and geocoding functions
"""

import asyncio
import requests
from typing import Optional, Dict, Any
from fastmcp.server.context import Context  # type: ignore

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
) -> Optional[Dict[str, Any]]:
    """
    Get user location from browser via WebSocket.
    
    Args:
        context: FastMCP context containing session information
        timeout: Timeout in seconds for waiting for browser response
    
    Returns:
        Location dictionary with latitude, longitude, and source='browser_geolocation'
        Returns None if browser location is unavailable
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
                
                return {
                    "latitude": location_data["latitude"],
                    "longitude": location_data["longitude"],
                    "accuracy": location_data.get("accuracy"),
                    "city": geocode_data.get("city"),
                    "region": geocode_data.get("region"),
                    "country": geocode_data.get("country"),
                    "source": "browser_geolocation",
                    "timestamp": event_info.get("timestamp")
                }
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
    include_reverse_geocoding: bool = False,
    prefer_browser: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Get user location with browser priority.
    
    Args:
        context: FastMCP context containing session information
        wait_time: Timeout for browser location (defaults to 10 seconds)
        include_reverse_geocoding: Not used (kept for compatibility)
        prefer_browser: If True, try browser location first (default True)
    
    Returns:
        Location dictionary with latitude, longitude, city, country, source, etc.
        Returns None if no location could be determined
    """
    try:
        # Try browser location first if preferred
        if prefer_browser:
            browser_loc = await get_browser_location(context, timeout=wait_time)
            if browser_loc:
                return browser_loc
        
        # Fallback to server IP geolocation
        return _fetch_server_location()

    except Exception:
        return None


async def get_user_city(context: Context, wait_time: int = 8) -> Optional[str]:
    """
    Get user's city name using server IP geolocation.
    
    Args:
        context: FastMCP context containing session information
        wait_time: Not used (kept for compatibility)
    
    Returns:
        City name string or None if could not be determined
    """
    location_info = await get_user_location(context, wait_time, include_reverse_geocoding=True)
    
    if location_info and location_info.get("city"):
        return location_info["city"]
    elif location_info and location_info.get("latitude") and location_info.get("longitude"):
        # Try reverse geocoding if city not available
        return _reverse_geocode(
            location_info["latitude"], 
            location_info["longitude"]
        )
    
    return None 