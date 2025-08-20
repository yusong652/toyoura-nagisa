"""Common utilities and models for places tools."""

from typing import List, Optional
from pydantic import BaseModel, Field
import googlemaps
from backend.config import get_auth_config

class Place(BaseModel):
    """Place model for validation"""
    place_id: str = Field(..., description="Unique identifier for the place")
    name: str = Field(..., description="Name of the place")
    address: str = Field(..., description="Formatted address of the place")
    location: dict = Field(..., description="Location coordinates (lat, lng)")
    types: List[str] = Field(default_factory=list, description="Types of the place")
    rating: Optional[float] = Field(None, description="Place rating (0-5)")
    user_ratings_total: Optional[int] = Field(None, description="Total number of user ratings")

def get_places_client():
    """Initialize Google Places API client"""
    api_key = get_auth_config().get('google_maps_api_key')
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not found in configuration")
    return googlemaps.Client(key=api_key)

# Common tags and annotations for places tools
COMMON_KWARGS_PLACES = dict(
    tags={"places", "google", "maps", "location", "search"}, 
    annotations={"category": "places", "tags": ["places", "google", "maps", "location", "search"]}
)