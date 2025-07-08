from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import os
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
    """
    Initialize and return a Google Places API client.
    Returns:
        googlemaps.Client: Google Places API client
    """
    api_key = get_auth_config().get('google_maps_api_key')
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not found in configuration")
    return googlemaps.Client(key=api_key)

def register_places_tools(mcp: FastMCP):
    """Register Google Places API based tools with proper tags synchronization."""
    
    common_kwargs_places = dict(
        tags={"places", "google", "maps", "location", "search"}, 
        annotations={"category": "places", "tags": ["places", "google", "maps", "location", "search"]}
    )

    @mcp.tool(**common_kwargs_places)
    def search_places(
        query: str = Field(..., description="Search query for places (e.g., 'restaurant', 'Starbucks')"),
        location: str = Field(..., description="Location name or coordinates in 'latitude,longitude' format (e.g., '40.7128,-74.0060')"),
        radius: int = Field(5000, description="Search radius in meters (default: 5000)"),
        max_results: int = Field(5, description="Maximum number of results to return (default: 5)")
    ) -> List[dict]:
        """
        Search for places using Google Places API.

        Args:
            query (str): Search query for places (e.g., 'restaurant', 'Starbucks').
            location (str): Location coordinates in 'latitude,longitude' format.
            radius (int): Search radius in meters.
            max_results (int): Maximum number of results to return.

        Returns:
            List[dict]: A list of place dictionaries. Each dictionary contains:
                - place_id (str): Unique identifier for the place
                - name (str): Name of the place
                - address (str): Formatted address
                - location (dict): Location coordinates
        """
        try:
            client = get_places_client()
            lat, lng = map(float, location.split(","))
            places_result = client.places(
                query=query,
                location=(lat, lng),
                radius=radius
            )
            places = []
            for place in places_result.get('results', [])[:max_results]:
                places.append({
                    'place_id': place['place_id'],
                    'name': place.get('name', ''),
                    'address': place.get('formatted_address', place.get('vicinity', '')),
                    'location': place['geometry']['location']
                })
            return places
        except Exception as e:
            return [{
                "error": f"Failed to search places: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }]

    @mcp.tool(**common_kwargs_places)
    def get_place_details(
        place_id: str = Field(..., description="Place ID to get details for")
    ) -> dict:
        """
        Get detailed information about a specific place using its Place ID.

        Args:
            place_id (str): Place ID to get details for.

        Returns:
            dict: A dictionary containing detailed place information:
                - place_id (str): Unique identifier for the place
                - name (str): Name of the place
                - address (str): Formatted address
                - location (dict): Location coordinates
                - editorial_summary (str): Editorial summary of the place
                - reviews (List[dict]): List of reviews for the place (each review text is at most 300 characters)
            If an error occurs, returns a dictionary containing:
                - error (str): Error message
                - timestamp (str): ISO format timestamp
        """
        try:
            client = get_places_client()
            details = client.place(place_id, fields=[
                'name', 'formatted_address', 'geometry',
                'editorial_summary', 'reviews'
            ])['result']
            # 限制每条review的text长度
            reviews = details.get('reviews', [])[:3]
            for review in reviews:
                if 'text' in review and len(review['text']) > 100:
                    review['text'] = review['text'][:100] + '...'
            place_info = {
                'place_id': place_id,
                'name': details.get('name', ''),
                'address': details.get('formatted_address', ''),
                'location': details['geometry']['location'],
                'editorial_summary': details.get('editorial_summary', {}).get('overview', ''),
                'reviews': reviews
            }
            return place_info
        except Exception as e:
            return {
                "error": f"Failed to get place details: {str(e)}",
                "timestamp": datetime.now().isoformat()
            } 