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

    common_kwargs_meta = dict(tags={"meta"}, annotations={"category": "meta"})

    @mcp.tool(**common_kwargs_meta)
    def search_tools_by_keywords(
        keywords: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃  🧠  META TOOL — **Dynamic Tool Discovery & Activation Gateway** ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

        **WHY use this meta-tool?**  
        Large Language Models (LLMs) cannot assume which helper tools are already
        loaded.  Before you attempt to call a domain-specific tool, use this
        function to *discover* and *activate* the most relevant tools for the
        user's current task.

        **HOW it works**  
        A semantic search is executed over the tool-vector database.  The
        database contains embeddings of every available tool's name, tags,
        description, docstring and parameter schema.  The *top-k* most similar
        tools are returned **and automatically become callable** in the same
        conversation turn.

        -------------------------------------------------------------------
        🔑 **Prompting guidelines (best practice)**
        -------------------------------------------------------------------
        1. **Use concise English keywords** – space-separated, no punctuation.  
           Good ► `"weather current temperature"`  
           Bad  ► `"Can you tell me the weather?"`
        2. **Include the *action* and the *domain*.**  
           e.g. `"email send"`, `"calendar create event"`, `"image generate"`.
        3. **Optional:** Add location or language specifiers (e.g. `"Tokyo"`,
           `"français"`) if the task is geo- or locale-sensitive.
        4. **If unsure what categories exist**, call
           `get_available_tool_categories()` first.

        -------------------------------------------------------------------
        🗂 **Current tool categories snapshot** *(non-exhaustive)*
        -------------------------------------------------------------------
        • communication   →  email, contacts, calendar
        • information     →  web-search, wiki
        • location        →  geolocation services
        • places          →  POI search, place details
        • scheduling      →  reminders, events
        • media           →  text-to-image generation
        • coding          →  file I/O, code execution
        • calculation     →  advanced calculator
        • memory          →  long-term memory read/write
        • time            →  current time, timezone conversion
        • weather         →  current weather, forecasts
        • utilities       →  unit conversion, miscellaneous helpers

        (Categories expand automatically when new tools are registered.)

        -------------------------------------------------------------------
        ✨ **Response schema**
        -------------------------------------------------------------------
        ```json
        {
          "tools": [
            {
              "id": "<unique-id>",
              "name": "<function-name>",
              "category": "<category>",
              "description": "<short description>",
              "docstring": "<full docstring>",
              "parameters": "<parameter JSON schema>",
              "tags": ["tag1", "tag2", …]
            }
          ],
          "total_found": <int>,
          "search_query": "<echo of your keywords>",
          "status": "success" | "error"
        }
        ```

        -------------------------------------------------------------------
        💡 **Example usage**
        -------------------------------------------------------------------
        1. User asks: *"Book a dinner for 2 tomorrow at 7pm in Osaka."*  
           LLM first calls:
           ```python
           search_tools_by_keywords("restaurant reservation places location")
           ```
           Then selects the returned `search_places` and `get_location` tools
           to accomplish the task.

        2. User asks: *"What will the weather be like this weekend in Paris?"*  
           ```python
           search_tools_by_keywords("weather forecast Paris")
           ```
           → returns `get_weather_forecast` tool.

        -------------------------------------------------------------------
        **Parameters**
        -------------------------------------------------------------------
        • `keywords` *(str, required)*  – Space-separated English keywords.  
        • `max_results` *(int, optional, default=5)* – Maximum number of tools to return.
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

    @mcp.tool(**common_kwargs_meta)
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