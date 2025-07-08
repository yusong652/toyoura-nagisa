from fastmcp import FastMCP
from typing import Dict, Any
import asyncio
import requests
from fastmcp.server.context import Context
from backend.nagisa_mcp.location_manager import get_location_manager, LocationData

__all__ = ["register_location_tools"]

# 获取位置管理器
a_location_manager = get_location_manager()


def _fetch_server_location() -> LocationData | None:
    """Fallback: geolocate server IP via ip-api.com"""
    try:
        resp = requests.get("http://ip-api.com/json", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return LocationData(
                latitude=data["lat"],
                longitude=data["lon"],
                source="server_ip_geolocation",
                city=data.get("city"),
                country=data.get("country"),
                region=data.get("regionName"),
            )
    except Exception as e:
        print(f"[_fetch_server_location] error: {e}")
    return None


def _reverse_geocode(lat: float, lon: float) -> Dict[str, str | None]:
    """Use OpenStreetMap Nominatim to reverse-geocode coordinates to city/region/country."""
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
    except Exception as e:
        print(f"[_reverse_geocode] failed: {e}")
    return {"city": None, "region": None, "country": None}


def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    common_kwargs_location = dict(
        tags={"location", "geolocation", "geography", "coordinates", "position"}, 
        annotations={"category": "location", "tags": ["location", "geolocation", "geography", "coordinates", "position"]}
    )

    @mcp.tool(**common_kwargs_location)
    async def get_location(context: Context) -> Dict[str, Any]:
        """Return client location information.

        The function attempts multiple fallbacks in order:
        1. Location previously reported by this session (browser geolocation).
        2. Request client browser location via WebSocket and wait up to 30s.
        3. Most recently reported global location from any session.
        4. Server IP geolocation (coarse fallback).
        """
        session_id = context.client_id
        if not session_id:
            return {"error": "Session ID missing"}

        loc = a_location_manager.get_session_location(session_id)
        if loc:
            return loc.to_dict()

        # ask browser to send location via websocket (non-blocking)
        app = getattr(context.fastmcp, "app", None)
        if app and hasattr(app.state, "connection_manager"):
            cm = app.state.connection_manager
            asyncio.create_task(cm.send_json(session_id, {"type": "REQUEST_LOCATION"}))

        wait, elapsed = 30, 0.5
        while elapsed < wait:
            await asyncio.sleep(0.5)
            elapsed += 0.5
            loc = a_location_manager.get_session_location(session_id)
            if loc:
                loc_dict = loc.to_dict()
                if loc.source == "browser_geolocation" and not loc.city:
                    loc_dict.update(_reverse_geocode(loc.latitude, loc.longitude))
                return loc_dict

        # global location fallback
        loc = a_location_manager.get_global_location()
        if loc:
            return loc.to_dict()

        # server IP fallback
        loc = _fetch_server_location()
        if loc:
            return loc.to_dict()

        return {"error": "Location could not be determined."} 