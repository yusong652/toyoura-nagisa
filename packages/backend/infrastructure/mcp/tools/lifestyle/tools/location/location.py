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

    @mcp.tool(
        name="get_location",
        description="Get the user's current geographic location",
        tags={"location", "geolocation", "geography", "coordinates", "position"}
    )
    async def get_location(context: Context) -> Dict[str, Any]:
        """Get the user's current geographic location.
        
        Returns latitude, longitude, city, region, and country information.
        Priority: Browser geolocation > Server IP location.
        """
        try:
            # Architecture guarantee: tool_manager.py always injects _meta.client_id
            session_id = context.client_id

            # Get user location using unified function
            print(f"[DEBUG] Getting user location for session {session_id}")
            location_data = await get_user_location(context, wait_time=30)
            
            if location_data:
                # Determine accuracy level based on accuracy field
                accuracy = "high" if (location_data.accuracy and location_data.accuracy != "low") else "low"
                
                # Build natural location description
                location_parts = []
                if location_data.city:
                    location_parts.append(location_data.city)
                if location_data.country:
                    location_parts.append(location_data.country)
                
                location_desc = ", ".join(location_parts) if location_parts else "Unknown location"
                
                # Create simple, natural language content for LLM
                llm_content = f"Location: {location_desc}\nCoordinates: {location_data.latitude:.2f}, {location_data.longitude:.2f}"
                if accuracy == "high":
                    llm_content += " (high accuracy from browser)"
                else:
                    llm_content += " (approximate from IP)"
                
                message = f"Location determined: {location_desc} ({accuracy} accuracy)"
                
                return success_response(
                    message,
                    llm_content={
                        "parts": [
                            {"type": "text", "text": llm_content}
                        ]
                    },
                    location_data={
                        "latitude": location_data.latitude,
                        "longitude": location_data.longitude,
                        "city": location_data.city,
                        "country": location_data.country,
                        "accuracy": accuracy
                    }
                )

            print(f"[DEBUG] All location methods failed, returning error")
            return error_response("Unable to determine location - both browser and server IP geolocation failed")

        except Exception as e:
            return error_response(f"Failed to get location: {str(e)}") 