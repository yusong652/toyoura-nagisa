"""
Location Tool Module - Geolocation services for position awareness
"""

from typing import Dict, Any
from fastmcp import FastMCP
import asyncio
import requests
from fastmcp.server.context import Context

from backend.nagisa_mcp.location_manager import get_location_manager, LocationData
from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.nagisa_mcp.utils.location_utils import get_user_location, _reverse_geocode_full

__all__ = ["register_location_tools"]

def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    # Get location manager instance
    location_manager = get_location_manager()

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
        """Get current location information with intelligent fallback strategies.

        ## Core Functionality
        - Attempts to get precise browser geolocation from client
        - Falls back to cached session or global location data
        - Uses server IP geolocation as final fallback
        - Returns coordinates with city/region/country details

        ## Return Value
        **For LLM:** Returns structured data with consistent format across all location tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "get_location",
            "session_id": "abc123",
            "location_source": "browser_geolocation",
            "timestamp": "2025-01-08T10:30:00.123"
          },
          "result": {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "city": "San Francisco",
            "region": "California", 
            "country": "United States",
            "accuracy": "high"
          },
          "summary": {
            "operation_type": "get_location",
            "success": true
          }
        }
        ```

        ## Strategic Usage
        Use this tool to **get location context** for weather, local services, timezone-aware scheduling, or location-based recommendations.
        """
        try:
            session_id = context.client_id
            if not session_id:
                return _error("Session ID missing")

            # Try session location first
            loc = location_manager.get_session_location(session_id)
            if loc:
                return _build_location_response(loc, session_id, "cached_session")

            # Request fresh location from browser
            app = getattr(context.fastmcp, "app", None)
            if app and hasattr(app.state, "connection_manager"):
                cm = app.state.connection_manager
                asyncio.create_task(cm.send_json(session_id, {"type": "REQUEST_LOCATION"}))

            # Wait for browser response
            wait_time, elapsed = 30, 0.5
            while elapsed < wait_time:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                loc = location_manager.get_session_location(session_id)
                if loc:
                    # Enhance with reverse geocoding if needed
                    if loc.source == "browser_geolocation" and not loc.city:
                        geocode_data = _reverse_geocode_full(loc.latitude, loc.longitude)
                        loc.city = geocode_data.get("city")
                        loc.region = geocode_data.get("region")
                        loc.country = geocode_data.get("country")
                    return _build_location_response(loc, session_id, "browser_geolocation")

            # Fallback to global location
            loc = location_manager.get_global_location()
            if loc:
                return _build_location_response(loc, session_id, "global_cache")

            # Final fallback to server IP
            loc = _fetch_server_location()
            if loc:
                return _build_location_response(loc, session_id, "server_ip_fallback")

            return _error("Location could not be determined")

        except Exception as e:
            return _error(f"Failed to get location: {str(e)}")

    def _build_location_response(loc: LocationData, session_id: str, source_type: str) -> Dict[str, Any]:
        """Build standardized location response"""
        from datetime import datetime
        
        timestamp = datetime.now().isoformat()
        
        # Determine accuracy level
        accuracy = "high" if source_type == "browser_geolocation" else "medium" if source_type in ["cached_session", "global_cache"] else "low"
        
        llm_content = {
            "operation": {
                "type": "get_location",
                "session_id": session_id,
                "location_source": source_type,
                "timestamp": timestamp
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