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
from backend.infrastructure.mcp.utils.location_utils import _reverse_geocode_full

__all__ = ["register_location_tools"]

def register_location_tools(mcp: FastMCP):
    """Register location-related tools with proper tags synchronization."""

    common_kwargs_location = dict(
        tags={"location", "geolocation", "geography", "coordinates", "position"}, 
        annotations={"category": "location", "tags": ["location", "geolocation", "geography", "coordinates", "position"]}
    )

    # Helper functions for consistent responses
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(
            status="error", 
            message=message, 
            error=message,
            llm_content={
                "operation": {
                    "type": "get_location",
                    "location_source": "error",
                },
                "result": None,
                "summary": {
                    "operation_type": "get_location",
                    "success": False,
                    "error": message
                }
            }
        ).model_dump()

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
        """
        try:
            session_id = context.client_id
            if not session_id:
                return _error("Session ID missing")

            # Request fresh location from browser using non-blocking event mechanism
            app = getattr(getattr(context, "fastmcp", None), "app", None)
            print(f"[DEBUG] App object: {app is not None}")
            
            if app and hasattr(app.state, "connection_manager"):
                print(f"[DEBUG] Connection manager available: {hasattr(app.state, 'connection_manager')}")
                # Import location response events storage
                from backend.presentation.websocket.router import _location_response_events
                location_events = _location_response_events
                
                # Create event for this location request
                location_event = asyncio.Event()
                location_events[session_id] = {
                    "event": location_event,
                    "location_data": None,
                    "success": False,
                    "timestamp": None
                }
                
                # Check if WebSocket connection exists
                cm = app.state.connection_manager  
                if session_id in cm.connections:
                    print(f"[DEBUG] WebSocket connection found for session {session_id}")
                    
                    # Send location request via WebSocket
                    await cm.send_json(session_id, {"type": "REQUEST_LOCATION"})
                    print(f"[DEBUG] WebSocket location request sent for session {session_id}")
                    
                    try:
                        # Wait for response with shorter timeout (5s for WebSocket)
                        print(f"[DEBUG] Waiting for WebSocket location response (5s timeout)...")
                        await asyncio.wait_for(location_event.wait(), timeout=5.0)
                        print(f"[DEBUG] WebSocket location event received")
                        
                        # Get the response data
                        event_info = location_events.get(session_id, {})
                        if event_info.get("success") and event_info.get("location_data"):
                            location_data = event_info["location_data"]
                            
                            # Create LocationData object from browser response
                            browser_loc = LocationData(
                                latitude=location_data["latitude"],
                                longitude=location_data["longitude"],
                                accuracy=location_data.get("accuracy"),
                                source="browser_geolocation",
                                session_id=session_id,
                                timestamp=event_info.get("timestamp", int(asyncio.get_event_loop().time()))
                            )
                            
                            # Add reverse geocoding to get city, region, country
                            try:
                                geocode_data = _reverse_geocode_full(browser_loc.latitude, browser_loc.longitude)
                                browser_loc.city = geocode_data.get("city")
                                browser_loc.region = geocode_data.get("region")
                                browser_loc.country = geocode_data.get("country")
                                print(f"[DEBUG] Reverse geocoding successful: {geocode_data}")
                            except Exception as e:
                                print(f"[DEBUG] Reverse geocoding failed: {e}")
                            
                            print(f"[DEBUG] WebSocket browser location success: lat={browser_loc.latitude}, lng={browser_loc.longitude}, city={browser_loc.city}")
                            return _build_location_response(browser_loc, session_id, "browser_geolocation")
                        else:
                            print(f"[DEBUG] WebSocket location failed: {event_info.get('error', 'No location data')}")
                            
                    except asyncio.TimeoutError:
                        print(f"[DEBUG] WebSocket location request timeout - will fallback")
                        
                    finally:
                        # Clean up the event
                        location_events.pop(session_id, None)
                else:
                    print(f"[DEBUG] No WebSocket connection for session {session_id} - using fallback immediately")
            else:
                print(f"[DEBUG] App or connection manager not available - using fallback immediately")
                
            # Fallback to server IP geolocation
            print(f"[DEBUG] Falling back to server IP geolocation")
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