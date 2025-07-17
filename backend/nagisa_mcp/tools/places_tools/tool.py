"""
Places Tools Module - Google Places API integration for location search
"""

from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from datetime import datetime
import googlemaps

from backend.config import get_auth_config
from backend.nagisa_mcp.utils.tool_result import ToolResult

class Place(BaseModel):
    """Place model for validation"""
    place_id: str = Field(..., description="Unique identifier for the place")
    name: str = Field(..., description="Name of the place")
    address: str = Field(..., description="Formatted address of the place")
    location: dict = Field(..., description="Location coordinates (lat, lng)")
    types: List[str] = Field(default_factory=list, description="Types of the place")
    rating: Optional[float] = Field(None, description="Place rating (0-5)")
    user_ratings_total: Optional[int] = Field(None, description="Total number of user ratings")

def register_places_tools(mcp: FastMCP):
    """Register Google Places API based tools with proper tags synchronization."""
    
    common_kwargs_places = dict(
        tags={"places", "google", "maps", "location", "search"}, 
        annotations={"category": "places", "tags": ["places", "google", "maps", "location", "search"]}
    )

    # Helper functions for consistent responses
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    def _get_places_client():
        """Initialize Google Places API client"""
        api_key = get_auth_config().get('google_maps_api_key')
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not found in configuration")
        return googlemaps.Client(key=api_key)

    @mcp.tool(**common_kwargs_places)
    def search_places(
        query: str = Field(..., description="Search query for places (e.g., 'restaurant', 'Starbucks near me')."),
        location: str = Field(..., description="Location coordinates in 'latitude,longitude' format (e.g., '40.7128,-74.0060')."),
        radius: int = Field(5000, ge=100, le=50000, description="Search radius in meters (100-50000)."),
        max_results: int = Field(5, ge=1, le=20, description="Maximum number of results to return (1-20).")
    ) -> Dict[str, Any]:
        """Search for places using Google Places API with location-based filtering.

        ## Core Functionality
        - Searches for places using Google Places API
        - Filters results by location and radius
        - Returns place information with coordinates and basic details
        - Supports various place types (restaurants, shops, services, etc.)

        ## Return Value
        **For LLM:** Returns structured data with consistent format across all location tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "search_places",
            "query": "restaurant",
            "location": "40.7128,-74.0060",
            "radius": 5000,
            "max_results": 5,
            "timestamp": "2025-01-08T10:30:00.123"
          },
          "result": {
            "places": [
              {
                "place_id": "ChIJd8BlQ2BZwokRAFUEcm_qrcA",
                "name": "Central Park Restaurant",
                "address": "123 Park Ave, New York, NY 10001",
                "location": {"lat": 40.7128, "lng": -74.0060},
                "rating": 4.5,
                "types": ["restaurant", "food"]
              }
            ],
            "total_found": 3,
            "search_limited": false
          },
          "summary": {
            "operation_type": "search_places",
            "success": true
          }
        }
        ```

        ## Strategic Usage
        Use this tool to **find nearby places** for recommendations, navigation, or location-based services.
        """
        try:
            # Validate location format
            try:
                lat, lng = map(float, location.split(","))
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    return _error("Invalid coordinates: latitude must be -90 to 90, longitude must be -180 to 180")
            except ValueError:
                return _error("Invalid location format. Use 'latitude,longitude' (e.g., '40.7128,-74.0060')")

            client = _get_places_client()
            
            # Search for places
            places_result = client.places(
                query=query,
                location=(lat, lng),
                radius=radius
            )
            
            # Format places for LLM consumption
            places = []
            for place in places_result.get('results', [])[:max_results]:
                formatted_place = {
                    'place_id': place['place_id'],
                    'name': place.get('name', ''),
                    'address': place.get('formatted_address', place.get('vicinity', '')),
                    'location': place['geometry']['location'],
                    'rating': place.get('rating'),
                    'types': place.get('types', [])
                }
                places.append(formatted_place)
            
            # Build structured response
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "search_places",
                    "query": query,
                    "location": location,
                    "radius": radius,
                    "max_results": max_results,
                    "timestamp": timestamp
                },
                "result": {
                    "places": places,
                    "total_found": len(places),
                    "search_limited": len(places) >= max_results
                },
                "summary": {
                    "operation_type": "search_places",
                    "success": True
                }
            }
            
            if places:
                message = f"Found {len(places)} places for '{query}' near {location}"
                high_rated = [p for p in places if p.get('rating', 0) >= 4.0]
                if high_rated:
                    message += f" ({len(high_rated)} highly rated)"
            else:
                message = f"No places found for '{query}' near {location}"
            
            return _success(
                message,
                llm_content,
                places=places,
                total_found=len(places),
                query=query,
                location=location
            )
            
        except Exception as e:
            return _error(f"Failed to search places: {str(e)}")

    @mcp.tool(**common_kwargs_places)
    def get_place_details(
        place_id: str = Field(..., description="Google Places API place ID to get detailed information for.")
    ) -> Dict[str, Any]:
        """Get comprehensive information about a specific place using its Place ID.

        ## Core Functionality
        - Retrieves detailed place information from Google Places API
        - Includes reviews, editorial summaries, and comprehensive metadata
        - Provides contact information and operational details
        - Returns structured data suitable for detailed place analysis

        ## Return Value
        **For LLM:** Returns structured data with consistent format across all location tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "get_place_details",
            "place_id": "ChIJd8BlQ2BZwokRAFUEcm_qrcA",
            "timestamp": "2025-01-08T10:30:00.123"
          },
          "result": {
            "place_details": {
              "place_id": "ChIJd8BlQ2BZwokRAFUEcm_qrcA",
              "name": "Central Park Restaurant",
              "address": "123 Park Ave, New York, NY 10001",
              "location": {"lat": 40.7128, "lng": -74.0060},
              "editorial_summary": "Popular restaurant with great views...",
              "reviews": [
                {
                  "author_name": "John Doe",
                  "rating": 5,
                  "text": "Excellent food and service..."
                }
              ],
              "review_count": 3
            }
          },
          "summary": {
            "operation_type": "get_place_details",
            "success": true
          }
        }
        ```

        ## Strategic Usage
        Use this tool to **get detailed place information** for comprehensive recommendations, reviews analysis, or detailed location context.
        """
        try:
            if not place_id or not place_id.strip():
                return _error("Place ID cannot be empty")

            client = _get_places_client()
            
            # Get place details
            details = client.place(place_id, fields=[
                'name', 'formatted_address', 'geometry',
                'editorial_summary', 'reviews', 'rating', 'user_ratings_total'
            ])['result']
            
            # Format reviews for LLM consumption (limit and truncate)
            reviews = details.get('reviews', [])[:3]
            for review in reviews:
                if 'text' in review and len(review['text']) > 150:
                    review['text'] = review['text'][:150] + '...'
            
            # Build place details structure
            place_details = {
                'place_id': place_id,
                'name': details.get('name', ''),
                'address': details.get('formatted_address', ''),
                'location': details.get('geometry', {}).get('location', {}),
                'editorial_summary': details.get('editorial_summary', {}).get('overview', ''),
                'reviews': [
                    {
                        'author_name': review.get('author_name', 'Anonymous'),
                        'rating': review.get('rating'),
                        'text': review.get('text', '')
                    } for review in reviews
                ],
                'rating': details.get('rating'),
                'review_count': len(reviews)
            }
            
            # Build structured response
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "get_place_details",
                    "place_id": place_id,
                    "timestamp": timestamp
                },
                "result": {
                    "place_details": place_details
                },
                "summary": {
                    "operation_type": "get_place_details",
                    "success": True
                }
            }
            
            place_name = place_details.get('name', 'Unknown place')
            message = f"Retrieved details for {place_name}"
            if place_details.get('rating'):
                message += f" (Rating: {place_details['rating']}/5)"
            
            return _success(
                message,
                llm_content,
                place_details=place_details,
                place_id=place_id,
                place_name=place_name
            )
            
        except Exception as e:
            return _error(f"Failed to get place details: {str(e)}") 