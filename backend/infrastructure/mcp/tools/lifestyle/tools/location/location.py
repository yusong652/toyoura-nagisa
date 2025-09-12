"""
Location Tool Module - Geolocation services for position awareness
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.mcp.location_manager import LocationData
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.location_utils import get_user_location

__all__ = ["register_location_tools"]

def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    common_kwargs_location = dict(
        tags={"location", "geolocation", "geography", "coordinates", "position"}, 
        annotations={"category": "location", "tags": ["location", "geolocation", "geography", "coordinates", "position"]}
    )

    @mcp.tool(**common_kwargs_location)
    async def get_location(context: Context) -> Dict[str, Any]:
        """Get the user's current geographic location.
        
        Returns latitude, longitude, city, region, and country information.
        Priority: Browser geolocation > Server IP location.
        """
        try:
            session_id = context.client_id
            if not session_id:
                return error_response("Session ID missing")

            # Get user location using unified function
            print(f"[DEBUG] Getting user location for session {session_id}")
            location_data = await get_user_location(context, wait_time=5)
            
            if location_data:
                # Determine accuracy level
                accuracy = "high" if location_data.source == "browser_geolocation" else "low"
                
                # Build natural location description
                location_parts = []
                if location_data.city:
                    location_parts.append(location_data.city)
                if location_data.region:
                    location_parts.append(location_data.region)
                if location_data.country:
                    location_parts.append(location_data.country)
                
                location_desc = ", ".join(location_parts) if location_parts else "Unknown location"
                
                # Create simple, natural language content for LLM
                llm_content = f"Location: {location_desc}\nCoordinates: {location_data.latitude:.6f}, {location_data.longitude:.6f}"
                if accuracy == "high":
                    llm_content += " (high accuracy from browser)"
                else:
                    llm_content += " (approximate from IP)"
                
                message = f"Location determined: {location_desc} ({accuracy} accuracy)"
                
                print(f"[DEBUG] Location found: {location_desc}, source: {location_data.source}")
                return success_response(
                    message,
                    llm_content,
                    location_data={
                        "latitude": location_data.latitude,
                        "longitude": location_data.longitude,
                        "city": location_data.city,
                        "region": location_data.region,
                        "country": location_data.country,
                        "source": location_data.source,
                        "accuracy": accuracy
                    }
                )

            print(f"[DEBUG] All location methods failed, returning error")
            return error_response("Unable to determine location - both browser and server IP geolocation failed")

        except Exception as e:
            return error_response(f"Failed to get location: {str(e)}") 