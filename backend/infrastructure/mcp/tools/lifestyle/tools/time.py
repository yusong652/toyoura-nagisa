from fastmcp import FastMCP
from datetime import datetime
import pytz
from typing import Optional
from timezonefinder import TimezoneFinder
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import ToolResult
from backend.infrastructure.mcp.utils.location_utils import get_user_location


def _error(message: str, error_details: Optional[str] = None) -> dict:
    """Create standardized error response."""
    data = {"error": message}
    if error_details:
        data["details"] = error_details
    
    error_msg = f"Time operation failed: {message}"
    llm_content = f"<error>{error_msg}</error>"
    
    return ToolResult(
        status="error",
        message=error_msg,
        llm_content=llm_content,
        error=message,
        data=data
    ).model_dump()

def _success(formatted_time: str, timezone_name: str, additional_formats: dict, location_info: Optional[dict] = None) -> dict:
    """Create standardized success response."""
    # Simple, natural string for LLM consumption
    llm_content = f"Current time in {timezone_name}: {formatted_time}"
    
    return ToolResult(
        status="success",
        message=f"Current time retrieved successfully ({timezone_name})",
        llm_content=llm_content,
        data={
            "primary_format": formatted_time,
            "timezone": timezone_name,
            "additional_formats": additional_formats,
            "location_info": location_info
        }
    ).model_dump()


def register_time_tools(mcp: FastMCP):
    """Register time related utilities with proper tags synchronization."""

    tf = TimezoneFinder()

    def _get_timezone_from_location(latitude: float, longitude: float) -> Optional[str]:
        """Convert latitude/longitude to timezone string"""
        try:
            return tf.timezone_at(lat=latitude, lng=longitude)
        except Exception:
            return None

    @mcp.tool(
        tags={"time", "datetime", "utilities", "system", "clock", "timezone", "location"}, 
        annotations={"category": "utilities", "tags": ["time", "datetime", "utilities", "system", "clock", "timezone", "location"]}
    )
    async def get_current_time(context: Context) -> dict:
        """Retrieve current time with automatic timezone detection from user location.
        
        Priority: Browser geolocation > Server IP location > Asia/Tokyo fallback.
        """
        try:
            location_info = None
            determined_timezone = None

            # Get user location (prioritizes browser, falls back to server IP)
            location_info = await get_user_location(context, wait_time=5, prefer_browser=True)
            
            if location_info and location_info.get("latitude") and location_info.get("longitude"):
                detected_tz = _get_timezone_from_location(
                    location_info["latitude"], 
                    location_info["longitude"]
                )
                if detected_tz:
                    determined_timezone = detected_tz
                else:
                    # Location found but timezone detection failed
                    determined_timezone = "Asia/Tokyo"
                    location_info["fallback_reason"] = "timezone_detection_failed"
            else:
                # No location could be determined
                determined_timezone = "Asia/Tokyo"
                location_info = {"source": "fallback", "fallback_reason": "all_location_detection_failed"}

            # Get current time based on determined timezone
            try:
                tz = pytz.timezone(determined_timezone)
                current_time = datetime.now(tz)
                timezone_name = determined_timezone
            except pytz.exceptions.UnknownTimeZoneError:
                return _error("Invalid timezone", f"Unknown timezone: {determined_timezone}")

            # Generate primary time format
            primary_format = current_time.strftime("%Y-%m-%d %H:%M:%S")

            return _success(primary_format, timezone_name, {}, location_info)
            
        except Exception as e:
            return _error("Time retrieval failed", str(e)) 