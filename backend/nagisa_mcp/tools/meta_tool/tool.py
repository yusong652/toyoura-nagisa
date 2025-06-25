"""
Meta Tool Module - Core tools for tool selection and discovery
"""

from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
import json
import sys
import os
from backend.config import TOOL_DB_PATH
from nagisa_mcp.tool_vectorizer import ToolVectorizer

# Add backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def register_meta_tools(mcp: FastMCP):
    """Register meta tools to the FastMCP server"""
    
    # Global tool vectorizer instance
    _vectorizer: Optional[ToolVectorizer] = None
    
    def get_vectorizer() -> ToolVectorizer:
        """Get the tool vectorizer instance"""
        nonlocal _vectorizer
        if _vectorizer is None:
            _vectorizer = ToolVectorizer(TOOL_DB_PATH)
        return _vectorizer

    @mcp.tool()
    def search_tools_by_keywords(
        keywords: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Meta Tool: Search for relevant tools based on keywords
        
        This is the core meta tool of aiNagisa for intelligent tool selection. When users enable tool mode,
        the system will call this tool to search for the most relevant tools based on user request keywords.
        
        Args:
            keywords: Search keywords describing the user's need or task (e.g., "time clock", "weather temperature", "web search", "email send")
            max_results: Maximum number of results to return
            
        Returns:
            Dict containing information about found tools, format as follows:
            {
                "tools": [
                    {
                        "id": "unique tool ID",
                        "name": "tool function name",
                        "category": "tool category",
                        "description": "tool description",
                        "docstring": "tool docstring",
                        "parameters": "tool parameter information",
                        "tags": ["tag1", "tag2"]
                    }
                ],
                "total_found": total number of tools found,
                "search_query": search query,
                "status": "success"
            }
        
        Example:
            User request: "What time is it now?"
            Call: search_tools_by_keywords("time clock current time")
            Returns: Information about time-related tools
            
            User request: "Search for weather information"
            Call: search_tools_by_keywords("weather temperature forecast")
            Returns: Information about weather-related tools
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
                    "docstring": metadata.get('docstring', ''),
                    "parameters": metadata.get('parameters', ''),
                    "tags": metadata.get('tags', [])
                }
                formatted_tools.append(formatted_tool)
            
            return {
                "tools": formatted_tools,
                "total_found": len(formatted_tools),
                "search_query": keywords,
                "status": "success"
            }
            
        except Exception as e:
            return {
                "tools": [],
                "total_found": 0,
                "search_query": keywords,
                "error": str(e),
                "status": "error"
            }

    @mcp.tool()
    def get_available_tool_categories() -> Dict[str, Any]:
        """
        Meta Tool: Get all available tool categories
        
        Returns all registered tool categories in the system to help LLM understand the available tool scope.
        
        Returns:
            Dict containing all available category information:
            {
                "categories": ["utilities", "information", "communication", ...],
                "total_categories": total number of categories,
                "status": "success"
            }
        """
        try:
            vectorizer = get_vectorizer()
            categories = vectorizer.list_all_categories()
            
            return {
                "categories": categories,
                "total_categories": len(categories),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "categories": [],
                "total_categories": 0,
                "error": str(e),
                "status": "error"
            } 