"""Common utilities for places tools."""

import googlemaps
from backend.config import get_auth_config

def get_places_client():
    """Initialize Google Places API client"""
    auth_config = get_auth_config()
    api_key = auth_config.google_maps_api_key
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not found in configuration")
    return googlemaps.Client(key=api_key)

# Common tags and annotations for places tools
COMMON_KWARGS_PLACES = dict(
    tags={"places", "google", "maps", "location", "search"}, 
    annotations={"category": "places", "tags": ["places", "google", "maps", "location", "search"]}
)