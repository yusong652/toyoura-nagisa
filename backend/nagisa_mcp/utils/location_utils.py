"""
Location Utilities - Shared location detection and geocoding functions
"""

import asyncio
import requests
from typing import Optional, Dict, Any
from fastmcp.server.context import Context  # type: ignore

from backend.nagisa_mcp.location_manager import get_location_manager


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


async def get_user_location(
    context: Context, 
    wait_time: int = 10,
    include_reverse_geocoding: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get user location from various sources with fallback strategy.
    
    Args:
        context: FastMCP context containing session information
        wait_time: Maximum time to wait for browser geolocation (seconds)
        include_reverse_geocoding: Whether to include reverse geocoding for coordinates
    
    Returns:
        Location dictionary with latitude, longitude, city, country, source, etc.
        Returns None if no location could be determined
    """
    try:
        session_id = getattr(context, 'client_id', None)
        if not session_id:
            return None

        location_manager = get_location_manager()

        # Try session location first
        loc = location_manager.get_session_location(session_id)
        if loc:
            location_data = {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "city": loc.city,
                "country": loc.country,
                "region": loc.region,
                "source": "cached_session"
            }
            
            # Add reverse geocoding if requested and city is missing
            if include_reverse_geocoding and not loc.city:
                geocode_data = _reverse_geocode_full(loc.latitude, loc.longitude)
                location_data.update(geocode_data)
            
            return location_data

        # Request fresh location from browser
        app = getattr(context.fastmcp, "app", None)
        if app and hasattr(app.state, "connection_manager"):
            cm = app.state.connection_manager
            asyncio.create_task(cm.send_json(session_id, {"type": "REQUEST_LOCATION"}))

            # Wait for browser response
            elapsed = 0.5
            while elapsed < wait_time:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                loc = location_manager.get_session_location(session_id)
                if loc:
                    location_data = {
                        "latitude": loc.latitude,
                        "longitude": loc.longitude,
                        "city": loc.city,
                        "country": loc.country,
                        "region": loc.region,
                        "source": "browser_geolocation"
                    }
                    
                    # Add reverse geocoding if requested and city is missing
                    if include_reverse_geocoding and not loc.city:
                        geocode_data = _reverse_geocode_full(loc.latitude, loc.longitude)
                        location_data.update(geocode_data)
                    
                    return location_data

        # Fallback to global location
        loc = location_manager.get_global_location()
        if loc:
            location_data = {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "city": loc.city,
                "country": loc.country,
                "region": loc.region,
                "source": "global_cache"
            }
            
            # Add reverse geocoding if requested and city is missing
            if include_reverse_geocoding and not loc.city:
                geocode_data = _reverse_geocode_full(loc.latitude, loc.longitude)
                location_data.update(geocode_data)
            
            return location_data

        # Final fallback to server IP
        return _fetch_server_location()

    except Exception:
        return None


async def get_user_city(context: Context, wait_time: int = 8) -> Optional[str]:
    """
    Get user's city name with intelligent fallback strategy.
    
    Args:
        context: FastMCP context containing session information
        wait_time: Maximum time to wait for browser geolocation (seconds)
    
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