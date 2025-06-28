from typing import Dict, Any, List
from fastmcp import FastMCP
from backend.memory import MemoryManager

# 初始化MemoryManager
memory_manager = MemoryManager()

def register_memory_tools(mcp: FastMCP):
    """Register memory search tools to MCP"""
    
    @mcp.tool(tags={"memory"}, annotations={"category": "memory"})
    def search_memory(query: str) -> List[Dict[str, Any]]:
        """
        Search through the conversation memory database using semantic similarity.

        Args:
            query (str): The search query or keywords to look for in the memory database.
                         For example: "user's preferences about coffee" or "previous discussion about project deadlines".

        Returns:
            List[Dict[str, Any]]: A list of relevant memories, each containing:
                - content: The actual text content of the memory
                - metadata: Additional information about the memory (timestamp, conversation_id, etc.)
                - relevance_score: The semantic similarity score (higher means more relevant)

        Example:
            search_memory("user's preferences about coffee")
            search_memory("previous discussion about project deadlines")
        """
        if not query or not query.strip():
            return []
        try:
            memories = memory_manager.search_memories(
                query=query,
                user_id="default",
                n_results=5  # 固定数量
            )
            
            # Format the results for better readability
            formatted_memories = []
            for memory in memories:
                formatted_memory = {
                    "content": memory["content"],
                    "metadata": {
                        "timestamp": memory["metadata"].get("timestamp"),
                        "conversation_id": memory["metadata"].get("conversation_id"),
                        "type": memory["metadata"].get("type")
                    },
                    "relevance_score": 1 - memory["distance"] if memory.get("distance") is not None else None
                }
                formatted_memories.append(formatted_memory)
            
            return formatted_memories
        except Exception as e:
            return [{
                "error": f"Failed to search memories: {str(e)}",
                "content": None,
                "metadata": None,
                "relevance_score": None
            }] 