from fastmcp import FastMCP
from datetime import datetime
import pytz
from fastmcp.server.context import Context  # type: ignore

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.location_utils import get_user_location
from backend.infrastructure.mcp.utils.time_utils import get_timezone_from_location


def register_time_tools(mcp: FastMCP):
    """Register time related utilities with proper tags synchronization."""


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

            if location_info and location_info.latitude and location_info.longitude:
                detected_tz = get_timezone_from_location(
                    location_info.latitude,
                    location_info.longitude
                )
                if detected_tz:
                    determined_timezone = detected_tz
                else:
                    # Location found but timezone detection failed
                    determined_timezone = "Asia/Tokyo"
            else:
                # No location could be determined
                determined_timezone = "Asia/Tokyo"
                location_info = None

            # Get current time based on determined timezone
            try:
                tz = pytz.timezone(determined_timezone)
                current_time = datetime.now(tz)
                timezone_name = determined_timezone
            except pytz.exceptions.UnknownTimeZoneError:
                return error_response(f"Invalid timezone: {determined_timezone}")

            # Generate primary time format
            primary_format = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Simple, natural string for LLM consumption
            llm_content = f"Current time in {timezone_name}: {primary_format}"

            return success_response(
                f"Current time retrieved successfully ({timezone_name})",
                llm_content,
                time_data={
                    "primary_format": primary_format,
                    "timezone": timezone_name
                }
            )
            
        except Exception as e:
            return error_response("Time retrieval failed") 