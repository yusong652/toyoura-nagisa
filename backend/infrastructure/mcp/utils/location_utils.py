"""
Location Utilities - Shared location detection and geocoding functions
"""

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


async def get_user_location(
    context: Context, 
    wait_time: int = 10,
    include_reverse_geocoding: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get user location using server IP geolocation.
    
    Args:
        context: FastMCP context containing session information (not used)
        wait_time: Not used (kept for compatibility)
        include_reverse_geocoding: Not used (kept for compatibility)
    
    Returns:
        Location dictionary with latitude, longitude, city, country, source, etc.
        Returns None if no location could be determined
    """
    try:
        # Use server IP geolocation
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