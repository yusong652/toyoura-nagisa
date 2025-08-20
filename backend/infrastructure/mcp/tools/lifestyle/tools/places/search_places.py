"""Google Places search tool."""

from typing import Dict, Any
from fastmcp import FastMCP
from pydantic import Field
from datetime import datetime

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.places_utils import get_places_client, COMMON_KWARGS_PLACES

def register_search_places_tool(mcp: FastMCP):
    """Register the search places tool."""
    
    @mcp.tool(**COMMON_KWARGS_PLACES)
    def search_places(
        query: str = Field(..., description="Search query for places (e.g., 'restaurant', 'Starbucks near me')."),
        location: str = Field(..., description="Location as coordinates 'latitude,longitude' (e.g., '40.7128,-74.0060') or place name (e.g., 'New York, NY', 'Tokyo')."),
        radius: int = Field(5000, ge=100, le=50000, description="Search radius in meters (100-50000)."),
        max_results: int = Field(5, ge=1, le=20, description="Maximum number of results to return (1-20).")
    ) -> Dict[str, Any]:
        """Search for places using Google Places API with location-based filtering.
        
        Searches for places by query and filters results by location and radius. Returns place information
        with coordinates, ratings, and basic details. Supports various place types.
        """
        try:
            client = get_places_client()
            
            # Parse location - coordinates (lat,lng) or place name
            if ',' in location and location.replace(',', '').replace('.', '').replace('-', '').replace(' ', '').isdigit():
                location_param = tuple(map(float, location.split(',')))
            else:
                location_param = location
            
            # Search for places
            places_result = client.places(
                query=query,
                location=location_param,
                radius=radius
            )
            
            # Format places for LLM consumption
            places = []
            for place in places_result.get('results', [])[:max_results]:
                formatted_place = {
                    'name': place.get('name', ''),
                    'address': place.get('formatted_address', place.get('vicinity', '')),
                    'location': place['geometry']['location'],
                    'rating': place.get('rating'),
                    'types': place.get('types', [])
                }
                places.append(formatted_place)
            
            # Build user-facing message and LLM content
            if places:
                message = f"Found {len(places)} places for '{query}' near {location}"
                high_rated = [p for p in places if p.get('rating', 0) >= 4.0]
                if high_rated:
                    message += f" ({len(high_rated)} highly rated)"
            else:
                message = f"No places found for '{query}' near {location}"
            
            if len(places) == 0:
                llm_content = "No places found."
            else:
                # Format places as readable text
                places_text = []
                for place in places:
                    place_line = f"• {place['name']}"
                    if place.get('rating'):
                        place_line += f" (★{place['rating']}/5)"
                    if place.get('address'):
                        place_line += f" - {place['address']}"
                    if place.get('types'):
                        # Show first 2 types to keep it concise
                        types_str = ", ".join(place['types'][:2])
                        place_line += f" [{types_str}]"
                    places_text.append(place_line)
                
                llm_content = "\n".join(places_text)
            
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