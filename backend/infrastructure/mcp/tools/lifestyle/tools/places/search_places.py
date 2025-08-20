"""Google Places search tool."""

from typing import Dict, Any
from fastmcp import FastMCP
from pydantic import Field
from datetime import datetime

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from .utils import get_places_client, COMMON_KWARGS_PLACES

def register_search_places_tool(mcp: FastMCP):
    """Register the search places tool."""
    
    @mcp.tool(**COMMON_KWARGS_PLACES)
    def search_places(
        query: str = Field(..., description="Search query for places (e.g., 'restaurant', 'Starbucks near me')."),
        location: str = Field(..., description="Location coordinates in 'latitude,longitude' format (e.g., '40.7128,-74.0060')."),
        radius: int = Field(5000, ge=100, le=50000, description="Search radius in meters (100-50000)."),
        max_results: int = Field(5, ge=1, le=20, description="Maximum number of results to return (1-20).")
    ) -> Dict[str, Any]:
        """Search for places using Google Places API with location-based filtering.
        
        Searches for places by query and filters results by location and radius. Returns place information
        with coordinates, ratings, and basic details. Supports various place types.
        """
        try:
            # Validate location format
            try:
                lat, lng = map(float, location.split(","))
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    return error_response("Invalid coordinates: latitude must be -90 to 90, longitude must be -180 to 180")
            except ValueError:
                return error_response("Invalid location format. Use 'latitude,longitude' (e.g., '40.7128,-74.0060')")

            client = get_places_client()
            
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
            
            return success_response(
                message,
                llm_content,
                places_data={
                    "places": places,
                    "total_found": len(places),
                    "query": query,
                    "location": location
                }
            )
            
        except Exception as e:
            return error_response(f"Failed to search places: {str(e)}")