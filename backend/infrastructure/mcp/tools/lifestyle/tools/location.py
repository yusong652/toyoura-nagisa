"""
Location Tool Module - Geolocation services for position awareness
"""

from typing import Dict, Any
from fastmcp import FastMCP
import asyncio
import requests
from fastmcp.server.context import Context

from backend.infrastructure.mcp.location_manager import LocationData
from backend.infrastructure.mcp.utils.tool_result import ToolResult
from backend.infrastructure.mcp.utils.location_utils import get_browser_location

__all__ = ["register_location_tools"]

def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    common_kwargs_location = dict(
        tags={"location", "geolocation", "geography", "coordinates", "position"}, 
        annotations={"category": "location", "tags": ["location", "geolocation", "geography", "coordinates", "position"]}
    )

    # Helper functions for consistent responses
    def _error(message: str) -> Dict[str, Any]:
        """Create standardized error response following coding tools pattern."""
        llm_content = f"<error>{message}</error>"
        return ToolResult(
            status="error", 
            message=message, 
            error=message,
            llm_content=llm_content
        ).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        """Create standardized success response following coding tools pattern."""
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    def _fetch_server_location() -> LocationData | None:
        """Fallback: geolocate server IP via ip-api.com"""
        try:
            print(f"[DEBUG] Attempting server IP geolocation via ip-api.com")
            resp = requests.get("http://ip-api.com/json", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            print(f"[DEBUG] IP geolocation response: {data}")
            
            if data.get("status") == "success":
                location_data = LocationData(
                    latitude=data["lat"],
                    longitude=data["lon"],
                    source="server_ip_geolocation",
                    city=data.get("city"),
                    country=data.get("country"),
                    region=data.get("regionName"),
                )
                print(f"[DEBUG] Server location success: lat={location_data.latitude}, lng={location_data.longitude}, city={location_data.city}")
                return location_data
            else:
                print(f"[DEBUG] IP geolocation failed with status: {data.get('status')}")
        except Exception as e:
            print(f"[DEBUG] IP geolocation error: {str(e)}")
        return None

    @mcp.tool(**common_kwargs_location)
    async def get_location(context: Context) -> Dict[str, Any]:
        """Get the user's current geographic location.
        
        Returns latitude, longitude, city, region, and country information.
        Priority: Browser geolocation > Server IP location.
        """
        try:
            session_id = context.client_id
            if not session_id:
                return _error("Session ID missing")

            # Try to get browser location first
            print(f"[DEBUG] Attempting to get browser location for session {session_id}")
            browser_loc_data = await get_browser_location(context, timeout=5.0)
            
            if browser_loc_data:
                # Create LocationData object from browser response
                browser_loc = LocationData(
                    latitude=browser_loc_data["latitude"],
                    longitude=browser_loc_data["longitude"],
                    accuracy=browser_loc_data.get("accuracy"),
                    source="browser_geolocation",
                    session_id=session_id,
                    timestamp=browser_loc_data.get("timestamp", int(asyncio.get_event_loop().time())),
                    city=browser_loc_data.get("city"),
                    region=browser_loc_data.get("region"),
                    country=browser_loc_data.get("country")
                )
                
                print(f"[DEBUG] Browser location success: lat={browser_loc.latitude}, lng={browser_loc.longitude}, city={browser_loc.city}")
                return _build_location_response(browser_loc, session_id, "browser_geolocation")
                
            # Fallback to server IP geolocation
            print(f"[DEBUG] Browser location unavailable, falling back to server IP geolocation")
            loc = _fetch_server_location()
            if loc:
                print(f"[DEBUG] Server IP geolocation succeeded, building response")
                return _build_location_response(loc, session_id, "server_ip_fallback")

            print(f"[DEBUG] All location methods failed, returning error")
            return _error("Unable to determine location - browser location unavailable, server IP geolocation failed")

        except Exception as e:
            return _error(f"Failed to get location: {str(e)}")

    def _build_location_response(loc: LocationData, session_id: str, source_type: str) -> Dict[str, Any]:
        """Build standardized location response"""
        # Determine accuracy level
        accuracy = "high" if source_type == "browser_geolocation" else "low"
        
        # Build natural location description
        location_parts = []
        if loc.city:
            location_parts.append(loc.city)
        if loc.region:
            location_parts.append(loc.region)
        if loc.country:
            location_parts.append(loc.country)
        
        location_desc = ", ".join(location_parts) if location_parts else "Unknown location"
        
        # Create simple, natural language content for LLM
        llm_content = f"Location: {location_desc}\nCoordinates: {loc.latitude:.6f}, {loc.longitude:.6f}"
        if accuracy == "high":
            llm_content += " (high accuracy from browser)"
        else:
            llm_content += " (approximate from IP)"
        
        message = f"Location determined: {location_desc} ({accuracy} accuracy)"
        
        result = _success(
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
        
        print(f"[DEBUG] Final location tool result: {result}")
        return result 