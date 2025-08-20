"""Google Places place details tool."""

from typing import Dict, Any
from fastmcp import FastMCP
from pydantic import Field
from datetime import datetime

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from .utils import get_places_client, COMMON_KWARGS_PLACES

def register_place_details_tool(mcp: FastMCP):
    """Register the place details tool."""
    
    @mcp.tool(**COMMON_KWARGS_PLACES)
    def get_place_details(
        place_id: str = Field(..., description="Google Places API place ID to get detailed information for.")
    ) -> Dict[str, Any]:
        """Get comprehensive information about a specific place using its Place ID.
        
        Retrieves detailed place information from Google Places API including reviews, editorial summaries,
        and comprehensive metadata. Returns structured data suitable for detailed place analysis.
        """
        try:
            if not place_id or not place_id.strip():
                return error_response("Place ID cannot be empty")

            client = get_places_client()
            
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
            
            return success_response(
                message,
                llm_content,
                place_details_data={
                    "place_details": place_details,
                    "place_id": place_id,
                    "place_name": place_name
                }
            )
            
        except Exception as e:
            return error_response(f"Failed to get place details: {str(e)}")