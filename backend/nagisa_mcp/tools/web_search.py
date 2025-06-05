from typing import List, Dict, Any
from googleapiclient.discovery import build
import os
import json
from dotenv import load_dotenv
import httpx
from bs4 import BeautifulSoup
import trafilatura
from trafilatura.metadata import extract_metadata

load_dotenv()

# Get Google API credentials from environment variables
GOOGLE_CUSTOM_SEARCH_API_KEY = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
GOOGLE_CUSTOM_SEARCH_API_ENGINE_ID = os.getenv("GOOGLE_CUSTOM_SEARCH_API_ENGINE_ID")

def search_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using Google Custom Search API.

    Args:
        query: The search query.
        max_results: Maximum number of results.

    Returns:
        A list of search results, each containing title, link, and snippet.
    """
    try:
        # Create the Custom Search API service
        service = build("customsearch", "v1", developerKey=GOOGLE_CUSTOM_SEARCH_API_KEY)

        # Execute the search
        result = service.cse().list(
            q=query,
            cx=GOOGLE_CUSTOM_SEARCH_API_ENGINE_ID,
            num=min(max_results, 10)  # Google API allows up to 10 results per request
        ).execute()

        # Process the search results
        items = result.get("items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
        return results
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]

async def get_webpage_content(url: str) -> dict:
    """
    Fetch and extract the main text content and metadata from a web page using trafilatura.

    Args:
        url: The web page URL.

    Returns:
        A dictionary containing the main text content and metadata of the web page.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(url, timeout=10.0)
            # 检查重定向
            if response.status_code in (301, 302, 303, 307, 308):
                return {
                    "error": (
                        "This page cannot be accessed directly (redirected or login required). "
                        "Please try the next link in the search results."
                    ),
                    "url": url,
                    "status_code": response.status_code,
                    "location": response.headers.get("location", "")
                }
            response.raise_for_status()
            # 使用 trafilatura 提取内容和元数据（JSON 格式）
            json_result = trafilatura.extract(
                response.text,
                output_format="json",
                with_metadata=True,
                include_comments=False,
                include_tables=True
            )
            if not json_result:
                return {
                    "error": "Failed to extract content",
                    "url": url
                }
            import json as _json
            try:
                data = _json.loads(json_result)
            except Exception as e:
                return {
                    "error": f"Failed to parse extracted JSON: {str(e)}",
                    "url": url
                }
            return {
                "content": data.get("text", "")[:2000],  # 限制内容长度
                "metadata": {
                    "title": data.get("title"),
                    "author": data.get("author"),
                    "date": data.get("date"),
                    "description": data.get("description"),
                    "categories": data.get("categories"),
                    "tags": data.get("tags"),
                    "url": url
                }
            }
    except Exception as e:
        return {
            "error": f"Failed to fetch web page content: {str(e)}",
            "url": url
        }

def register_web_search_tools(mcp):
    """Register web search related tools to MCP."""

    @mcp.tool()
    def web_search(query: str, max_results: int = 5) -> str:
        """
        Search the web using Google Custom Search API and return a JSON array of results.
        Each result contains title, link, and snippet.
        If you need to fetch the full content and metadata of a specific web page from the search results, you must call the get_webpage tool with the corresponding URL.
        Args:
            query: The search query.
            max_results: Maximum number of results (default 5).
        Returns:
            JSON string of search results, e.g.:
            [
                {"title": "...", "link": "...", "snippet": "..."},
                ...
            ]
        """
        results = search_web(query, max_results)
        if "error" in results[0]:
            return results[0]["error"]

        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    async def get_webpage(url: str) -> str:
        """
        Fetch and return the main content and metadata (such as title, author, date, description, etc.) of a specific web page.
        Use this tool when you need to extract the full text and metadata from a given web page URL, for example after obtaining a link from web_search.
        Args:
            url: The web page URL.
        Returns:
            Formatted string containing the main content and metadata of the web page.
        """
        result = await get_webpage_content(url)
        
        if "error" in result:
            return result["error"]
            
        # 格式化输出
        metadata = result["metadata"]
        formatted_output = []
        
        # 添加元数据
        if metadata["title"]:
            formatted_output.append(f"Title: {metadata['title']}")
        if metadata["author"]:
            formatted_output.append(f"Author: {metadata['author']}")
        if metadata["date"]:
            formatted_output.append(f"Date: {metadata['date']}")
        if metadata["description"]:
            formatted_output.append(f"Description: {metadata['description']}")
            
        # 添加内容
        formatted_output.append("\nContent:")
        formatted_output.append(result["content"])
        
        return "\n".join(formatted_output) 