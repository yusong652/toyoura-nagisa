from fastmcp import FastMCP
from datetime import datetime
import time
import pytz
from typing import Optional
import asyncio
import requests
from timezonefinder import TimezoneFinder
from fastmcp.server.context import Context  # type: ignore

from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.nagisa_mcp.location_manager import get_location_manager


def _error(message: str, error_details: Optional[str] = None) -> dict:
    """Create standardized error response."""
    data = {"error": message}
    if error_details:
        data["details"] = error_details
    
    return ToolResult(
        status="error",
        message=f"Time operation failed: {message}",
        llm_content={
            "operation": "get_current_time",
            "result": {
                "error": message,
                "details": error_details
            },
            "summary": f"Unable to retrieve time: {message}"
        },
        data=data
    ).model_dump()

def _success(formatted_time: str, timezone_name: str, additional_formats: dict, location_info: Optional[dict] = None) -> dict:
    """Create standardized success response."""
    summary = f"Current time: {formatted_time} ({timezone_name})"
    if location_info:
        summary += f" - {location_info.get('source', 'unknown')} location"
    
    return ToolResult(
        status="success",
        message=f"Current time retrieved successfully ({timezone_name})",
        llm_content={
            "operation": "get_current_time",
            "result": {
                "current_time": formatted_time,
                "timezone": timezone_name,
                "formats": additional_formats,
                "location_source": location_info.get("source") if location_info else "manual_override"
            },
            "summary": summary
        },
        data={
            "primary_format": formatted_time,
            "timezone": timezone_name,
            "additional_formats": additional_formats,
            "location_info": location_info
        }
    ).model_dump()


def register_time_tools(mcp: FastMCP):
    """Register time related utilities with proper tags synchronization."""

    # Get location manager instance
    location_manager = get_location_manager()
    tf = TimezoneFinder()

    def _fetch_server_location():
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
                    "source": "server_ip"
                }
        except Exception:
            pass
        return None

    async def _get_user_location(context: Context):
        """Get user location from various sources with fallback strategy"""
        try:
            session_id = getattr(context, 'client_id', None)
            if not session_id:
                return None

            # Try session location first
            loc = location_manager.get_session_location(session_id)
            if loc:
                return {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "city": loc.city,
                    "country": loc.country,
                    "source": "cached_session"
                }

            # Request fresh location from browser
            app = getattr(context.fastmcp, "app", None)
            if app and hasattr(app.state, "connection_manager"):
                cm = app.state.connection_manager
                asyncio.create_task(cm.send_json(session_id, {"type": "REQUEST_LOCATION"}))

                # Wait for browser response (shorter wait for time tool)
                wait_time, elapsed = 10, 0.5
                while elapsed < wait_time:
                    await asyncio.sleep(0.5)
                    elapsed += 0.5
                    loc = location_manager.get_session_location(session_id)
                    if loc:
                        return {
                            "latitude": loc.latitude,
                            "longitude": loc.longitude,
                            "city": loc.city,
                            "country": loc.country,
                            "source": "browser_geolocation"
                        }

            # Fallback to global location
            loc = location_manager.get_global_location()
            if loc:
                return {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "city": loc.city,
                    "country": loc.country,
                    "source": "global_cache"
                }

            # Final fallback to server IP
            return _fetch_server_location()

        except Exception:
            return None

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
    async def get_current_time(context: Context, timezone: Optional[str] = None) -> dict:
        """Retrieve the current system time with automatic timezone detection from user location.

        Core Functionality:
        Automatically detects user's timezone from browser geolocation, providing current date and time information in multiple useful formats. Falls back to Tokyo timezone if location detection fails or explicit timezone is specified. Supports timezone conversion and includes both human-readable formats and machine-readable timestamps.

        Return Value:
        Success response:
        {
            "operation": "get_current_time",
            "result": {
                "current_time": "2024-01-15 14:30:00",
                "timezone": "America/New_York",
                "formats": {
                    "iso_format": "2024-01-15T14:30:00-05:00",
                    "timestamp": 1705340200,
                    "human_readable": "Monday, January 15, 2024 at 02:30:00 PM",
                    "date_only": "2024-01-15",
                    "time_only": "14:30:00",
                    "utc_iso": "2024-01-15T19:30:00Z",
                    "timezone_offset": "-0500"
                },
                "location_source": "browser_geolocation"
            },
            "summary": "Current time: 2024-01-15 14:30:00 (America/New_York) - browser_geolocation location"
        }

        Error response:
        {
            "operation": "get_current_time", 
            "result": {
                "error": "Invalid timezone",
                "details": "Unknown timezone: InvalidZone"
            },
            "summary": "Unable to retrieve time: Invalid timezone"
        }

        Strategic Usage:
        • Essential for scheduling and time-sensitive operations with automatic localization
        • Automatically detects user's timezone from browser for personalized time display
        • Falls back to Tokyo time (Asia/Tokyo) if location detection fails
        • Use for logging timestamps and temporal context
        • Helpful for timezone-aware applications and international coordination
        • Provides multiple formats for different display and processing needs
        • Can override automatic detection with specific timezone parameter

        Args:
            timezone: Optional timezone override. If not provided, will auto-detect from user location.
                     Use 'Local' for system timezone. Examples: 'UTC', 'US/Eastern', 'Asia/Shanghai', 'Local'
        """
        try:
            location_info = None
            determined_timezone = timezone

            # If no timezone specified, try to detect from user location
            if not timezone:
                location_info = await _get_user_location(context)
                if location_info and location_info.get("latitude") and location_info.get("longitude"):
                    detected_tz = _get_timezone_from_location(
                        location_info["latitude"], 
                        location_info["longitude"]
                    )
                    if detected_tz:
                        determined_timezone = detected_tz
                    else:
                        # Fallback to Tokyo if timezone detection fails
                        determined_timezone = "Asia/Tokyo"
                        location_info["fallback_reason"] = "timezone_detection_failed"
                else:
                    # Fallback to Tokyo if location detection fails
                    determined_timezone = "Asia/Tokyo"
                    location_info = {"source": "fallback", "fallback_reason": "location_detection_failed"}

            # Get current time based on determined timezone
            if determined_timezone and determined_timezone.lower() != "local":
                try:
                    tz = pytz.timezone(determined_timezone)
                    current_time = datetime.now(tz)
                    timezone_name = determined_timezone
                except pytz.exceptions.UnknownTimeZoneError:
                    return _error("Invalid timezone", f"Unknown timezone: {determined_timezone}")
            else:
                # Use local timezone (when timezone is "Local")
                current_time = datetime.now()
                timezone_name = "Local"
                
                # Try to get local timezone name
                try:
                    local_tz = current_time.astimezone().tzinfo.tzname(current_time)
                    if local_tz:
                        timezone_name = f"Local ({local_tz})"
                except:
                    pass

            # Generate multiple time formats
            primary_format = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            additional_formats = {
                "iso_format": current_time.isoformat(),
                "timestamp": int(current_time.timestamp()),
                "human_readable": current_time.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
                "date_only": current_time.strftime("%Y-%m-%d"),
                "time_only": current_time.strftime("%H:%M:%S"),
                "utc_iso": datetime.utcnow().isoformat() + "Z"
            }
            
            # Add timezone offset if available
            try:
                offset = current_time.strftime("%z")
                if offset:
                    additional_formats["timezone_offset"] = offset
            except:
                pass

            return _success(primary_format, timezone_name, additional_formats, location_info)
            
        except Exception as e:
            return _error("Time retrieval failed", str(e)) 