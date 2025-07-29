"""
Meta Tool Module - Core tools for tool selection and discovery
"""

from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field
import sys
import os

from backend.config import TOOL_DB_PATH
from ...tool_vectorizer import ToolVectorizer
from backend.infrastructure.mcp.utils.tool_result import ToolResult

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
        
        Performs semantic search over tool vector database and returns most relevant tools.
        Use before calling domain-specific tools to ensure availability.
        """
        try:
            vectorizer = get_vectorizer()
            
            # Step 1: Execute semantic search to get tool names and basic info
            search_results = vectorizer.search_tools(
                query=keywords,
                n_results=max_results
            )
            
            # Step 2: Get all MCP tools to create a live mapping
            # Since we're already in MCP context, get tools directly from the server
            from backend.infrastructure.mcp.smart_mcp_server import mcp as GLOBAL_MCP
            
            # Get all registered tools directly from the MCP server
            try:
                # Use FastMCP's get_tools() method to access live tools
                all_mcp_tools = GLOBAL_MCP.get_tools()
                
                # Create mapping: tool_name -> live_tool_object
                mcp_tools_map = {tool.name: tool for tool in all_mcp_tools}
                
                if len(mcp_tools_map) == 0:
                    print(f"[WARNING] No MCP tools found in live server")
                
            except Exception as e:
                print(f"[WARNING] Could not access live MCP tools: {e}")
                mcp_tools_map = {}
            
            # Step 3: Combine search results with live MCP data
            formatted_tools = []
            for tool_info in search_results:
                metadata = tool_info.get('metadata', {})
                tool_name = metadata.get('function_name', 'unknown')
                
                # Get live tool data from MCP server (if available)
                live_tool = mcp_tools_map.get(tool_name)
                
                # Parse tags from vector database (for search accuracy)
                tags = []
                if 'tags' in metadata:
                    try:
                        import json
                        tags = json.loads(metadata['tags']) if isinstance(metadata['tags'], str) else metadata['tags']
                        if not isinstance(tags, list):
                            tags = []
                    except (json.JSONDecodeError, TypeError):
                        tags = []
                
                if live_tool:
                    # Use live data from MCP server (guaranteed fresh and accurate)
                    formatted_tool = {
                        "id": tool_info['id'],
                        "name": live_tool.name,
                        "category": metadata.get('category', 'general'),  # Keep vector DB category for consistency
                        "description": live_tool.description or tool_info.get('description', ''),
                        "docstring": metadata.get('docstring', ''),  # Keep vector DB docstring
                        "parameters": getattr(live_tool, 'inputSchema', {}),  # Live schema from MCP
                        "tags": tags  # Keep vector DB tags for search context
                    }
                else:
                    # Fallback: tool not found in MCP (maybe disabled), use vector DB data
                    # but mark parameters as potentially stale
                    parameters = {}
                    if 'parameters' in metadata:
                        try:
                            import json
                            parameters = json.loads(metadata['parameters']) if isinstance(metadata['parameters'], str) else metadata['parameters']
                        except (json.JSONDecodeError, TypeError):
                            parameters = {}
                    
                    formatted_tool = {
                        "id": tool_info['id'],
                        "name": tool_name,
                        "category": metadata.get('category', 'general'),
                        "description": tool_info.get('description', ''),
                        "docstring": metadata.get('docstring', ''),
                        "parameters": parameters,  # Potentially stale data
                        "tags": tags,
                        "_warning": "Tool not found in live MCP server - data may be outdated"
                    }
                
                formatted_tools.append(formatted_tool)
            
            # Build structured response following unified standard
            
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
                    "max_results": max_results
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
        
        Returns all registered tool categories in the system.
        Use before search_tools() to understand available domains.
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
            
            llm_content = {
                "operation": {
                    "type": "category_discovery"
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