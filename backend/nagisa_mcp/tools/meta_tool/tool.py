"""
Meta Tool Module - Core tools for tool selection and discovery
"""

from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field
import sys
import os
from datetime import datetime

from backend.config import TOOL_DB_PATH
from ...tool_vectorizer import ToolVectorizer
from backend.nagisa_mcp.utils.tool_result import ToolResult

# Add backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def register_meta_tools(mcp: FastMCP):
    """Register meta tools with proper tags synchronization."""
    
    # Global tool vectorizer instance
    _vectorizer: Optional[ToolVectorizer] = None
    
    def get_vectorizer() -> ToolVectorizer:
        """Get the tool vectorizer instance"""
        nonlocal _vectorizer
        if _vectorizer is None:
            _vectorizer = ToolVectorizer(TOOL_DB_PATH)
        return _vectorizer

    common_kwargs_meta = dict(
        tags={"meta", "discovery", "search", "tools", "vectorization"}, 
        annotations={"category": "meta", "tags": ["meta", "discovery", "search", "tools", "vectorization"]}
    )

    @mcp.tool(**common_kwargs_meta)
    def search_tools(
        keywords: str = Field(
            ...,
            description="Space-separated English keywords for semantic tool search (e.g., 'weather forecast', 'email send', 'calendar create')."
        ),
        max_results: int = Field(
            5,
            ge=1,
            le=20,
            description="Maximum number of tools to return from search results."
        )
    ) -> Dict[str, Any]:
        """Discover and activate relevant tools using semantic search.

        ## Core Functionality
        - Performs semantic search over tool vector database
        - Returns most relevant tools for given keywords
        - Automatically activates discovered tools for immediate use
        - Supports domain-specific tool discovery (coding, communication, etc.)

        ## Strategic Usage
        - Use before calling domain-specific tools to ensure availability
        - Include action + domain in keywords: `"email send"`, `"image generate"`
        - Combine with `get_available_tool_categories()` for comprehensive discovery

        ## Return Value
        Returns structured tool discovery results with comprehensive metadata.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "tool_discovery",
            "keywords": "weather forecast",
            "max_results": 5,
            "timestamp": "2025-01-08T10:30:00.123"
          },
          "result": {
            "tools_found": ["weather_forecast", "get_weather"],
            "search_limited": false
          },
          "summary": {
            "operation_type": "tool_discovery",
            "success": true
          }
        }
        ```

        **Optional Fields:**
        - `result.guidance`: Present only when `search_limited` is true, provides optimization suggestions

        ## Examples
        ```python
        # Find weather tools
        search_tools("weather forecast Paris")
        
        # Find coding tools
        search_tools("file edit replace")
        
        # Find communication tools
        search_tools("email send calendar")
        ```
        """
        try:
            vectorizer = get_vectorizer()
            
            # Execute tool search
            tools = vectorizer.search_tools(
                query=keywords,
                n_results=max_results
            )
            
            # Format return results
            formatted_tools = []
            for tool_info in tools:
                metadata = tool_info.get('metadata', {})
                formatted_tool = {
                    "id": tool_info['id'],
                    "name": metadata.get('function_name', 'unknown'),
                    "category": metadata.get('category', 'general'),
                    "description": tool_info.get('description', ''),
                    "tags": metadata.get('tags', [])
                }
                formatted_tools.append(formatted_tool)
            
            # Build structured response following unified standard
            timestamp = datetime.now().isoformat()
            
            # Extract tool names for better LLM understanding
            tools_found = [tool.get("name", "unknown") for tool in formatted_tools]
            
            # Prepare guidance for search limits
            guidance_message = ""
            if len(formatted_tools) >= max_results:
                guidance_message = f"Search limited to {max_results} results. Consider increasing max_results parameter (up to 20) to find more tools."
            
            llm_content = {
                "operation": {
                    "type": "tool_discovery",
                    "keywords": keywords,
                    "max_results": max_results,
                    "timestamp": timestamp
                },
                "result": {
                    "tools_found": tools_found,
                    "search_limited": len(formatted_tools) >= max_results,
                    "guidance": guidance_message if guidance_message else None
                },
                "summary": {
                    "operation_type": "tool_discovery",
                    "success": True
                }
            }
            
            # Clean up None values
            if not llm_content["result"]["guidance"]:
                del llm_content["result"]["guidance"]
            
            message = f"Found {len(formatted_tools)} relevant tools for '{keywords}'"
            if len(formatted_tools) >= max_results:
                message += f" (limited to {max_results}; increase max_results to find more)"
            
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data={
                    "tools": formatted_tools,
                    "tools_found": tools_found,
                    "search_query": keywords
                }
            ).model_dump()
            
        except Exception as e:
            return ToolResult(
                status="error",
                message=f"Tool discovery failed: {str(e)}",
                error=str(e),
                data={
                    "tools": [],
                    "tools_found": [],
                    "search_query": keywords
                }
            ).model_dump()

    @mcp.tool(**common_kwargs_meta)
    def get_available_tool_categories() -> Dict[str, Any]:
        """Get comprehensive list of available tool categories.

        ## Core Functionality
        - Returns all registered tool categories in the system
        - Provides category overview for strategic tool discovery
        - Helps LLM understand available tool scope and capabilities

        ## Strategic Usage
        - Use before `search_tools()` to understand available domains
        - Helps formulate better search keywords based on available categories
        - Provides context for tool selection strategy

        ## Return Value
        Returns structured category information with comprehensive metadata.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "category_discovery",
            "timestamp": "2025-01-08T10:30:00.123"
          },
          "result": {
            "total_categories": 4,
            "categories_available": ["coding", "communication", "information", "weather"]
          },
          "summary": {
            "operation_type": "category_discovery",
            "success": true
          }
        }
        ```

        ## Examples
        ```python
        # Get all available categories
        categories = get_available_tool_categories()
        
        # Use categories to guide tool search
        if "weather" in categories["result"]["categories_available"]:
            search_tools("weather forecast")
        ```
        """
        try:
            vectorizer = get_vectorizer()
            categories = vectorizer.list_all_categories()
            
            # Build category details for better context
            category_details = {
                "coding": "File I/O, code execution, development tools",
                "communication": "Email, contacts, calendar management", 
                "information": "Web search, knowledge retrieval",
                "weather": "Weather forecasts, climate data",
                "location": "Geolocation services, place data",
                "places": "POI search, place details",
                "scheduling": "Reminders, events, time management",
                "media": "Text-to-image generation, media tools",
                "calculation": "Advanced calculator, math operations",
                "memory": "Long-term memory read/write",
                "time": "Current time, timezone conversion",
                "utilities": "Unit conversion, miscellaneous helpers"
            }
            
            # Filter to only available categories
            available_details = {cat: category_details.get(cat, "General purpose tools") 
                               for cat in categories}
            
            # Build structured response following unified standard
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "category_discovery",
                    "timestamp": timestamp
                },
                "result": {
                    "categories_available": categories,
                    "category_count": len(categories)
                },
                "summary": {
                    "operation_type": "category_discovery",
                    "success": True
                }
            }
            
            message = f"Found {len(categories)} available tool categories"
            
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data={
                    "categories": categories,
                    "category_count": len(categories),
                    "category_details": available_details
                }
            ).model_dump()
            
        except Exception as e:
            return ToolResult(
                status="error",
                message=f"Category discovery failed: {str(e)}",
                error=str(e),
                data={
                    "categories": [],
                    "category_count": 0,
                    "category_details": {}
                }
            ).model_dump() 