"""
Location Tool Module - Geolocation services for position awareness
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP
import asyncio
import requests
import time
from threading import RLock
from fastmcp.server.context import Context

from backend.nagisa_mcp.location_manager import LocationData
from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.nagisa_mcp.utils.location_utils import get_user_location, _reverse_geocode_full

# Temporary location storage for tool calls only
_temp_locations: Dict[str, LocationData] = {}
_temp_lock = RLock()

def store_temp_location(session_id: str, location_data: Dict[str, Any]) -> None:
    """Store location temporarily for current tool call"""
    with _temp_lock:
        _temp_locations[session_id] = LocationData(
            latitude=location_data['latitude'],
            longitude=location_data['longitude'],
            accuracy=location_data.get('accuracy'),
            source="browser_geolocation",
            session_id=session_id,
            timestamp=int(time.time())
        )

def get_temp_location(session_id: str) -> Optional[LocationData]:
    """Get temporarily stored location"""
    with _temp_lock:
        return _temp_locations.get(session_id)

def clear_temp_location(session_id: str) -> None:
    """Clear temporary location after tool call"""
    with _temp_lock:
        _temp_locations.pop(session_id, None)

__all__ = ["register_location_tools"]

def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    common_kwargs_location = dict(
        tags={"location", "geolocation", "geography", "coordinates", "position"}, 
        annotations={"category": "location", "tags": ["location", "geolocation", "geography", "coordinates", "position"]}
    )

    # Helper functions for consistent responses
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

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
        except Exception:
            pass
        return None

    @mcp.tool(**common_kwargs_location)
    async def get_location(context: Context) -> Dict[str, Any]:
        """Get current location information.
        
        Requests geolocation from browser client and uses server IP geolocation as fallback.
        Returns coordinates with city/region/country details.
        """
        try:
            session_id = context.client_id
            if not session_id:
                return _error("Session ID missing")

            # Request fresh location from browser
            app = getattr(context.fastmcp, "app", None)
            if app and hasattr(app.state, "connection_manager"):
                cm = app.state.connection_manager
                await cm.send_json(session_id, {"type": "REQUEST_LOCATION"})
                
                # Wait for browser response
                wait_time = 10
                elapsed = 0
                while elapsed < wait_time:
                    await asyncio.sleep(0.5)
                    elapsed += 0.5
                    
                    # Check for browser response in temporary storage
                    temp_loc = get_temp_location(session_id)
                    if temp_loc:
                        # Enhance with reverse geocoding if needed
                        if temp_loc.source == "browser_geolocation" and not temp_loc.city:
                            try:
                                geocode_data = _reverse_geocode_full(temp_loc.latitude, temp_loc.longitude)
                                temp_loc.city = geocode_data.get("city")
                                temp_loc.region = geocode_data.get("region")
                                temp_loc.country = geocode_data.get("country")
                            except Exception:
                                pass
                        
                        # Clear temporary storage and return result
                        clear_temp_location(session_id)
                        return _build_location_response(temp_loc, session_id, "browser_geolocation")
                
            # Fallback to server IP geolocation
            loc = _fetch_server_location()
            if loc:
                return _build_location_response(loc, session_id, "server_ip_fallback")

            return _error("Location could not be determined")

        except Exception as e:
            return _error(f"Failed to get location: {str(e)}")

    def _build_location_response(loc: LocationData, session_id: str, source_type: str) -> Dict[str, Any]:
        """Build standardized location response"""
        # Determine accuracy level
        accuracy = "high" if source_type == "browser_geolocation" else "low"
        
        llm_content = {
            "operation": {
                "type": "get_location",
                "location_source": source_type,
            },
            "result": {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "city": loc.city,
                "region": loc.region,
                "country": loc.country,
                "accuracy": accuracy
            },
            "summary": {
                "operation_type": "get_location",
                "success": True
            }
        }
        
        location_desc = f"{loc.city or 'Unknown city'}"
        if loc.region:
            location_desc += f", {loc.region}"
        if loc.country:
            location_desc += f", {loc.country}"
        
        message = f"Location determined: {location_desc} ({accuracy} accuracy)"
        
        return _success(
            message,
            llm_content,
            latitude=loc.latitude,
            longitude=loc.longitude,
            city=loc.city,
            region=loc.region,
            country=loc.country,
            source=source_type,
            accuracy=accuracy
        ) 