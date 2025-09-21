"""Time utilities - Timezone detection and time formatting functions."""

from typing import Optional
from timezonefinder import TimezoneFinder

# Initialize TimezoneFinder instance
_tf = TimezoneFinder()

def get_timezone_from_location(latitude: float, longitude: float) -> Optional[str]:
    """Convert latitude/longitude to timezone string using TimezoneFinder.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        Timezone string (e.g., 'America/New_York') or None if detection fails
    """
    try:
        return _tf.timezone_at(lat=latitude, lng=longitude)
    except Exception:
        return None