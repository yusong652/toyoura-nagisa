"""
Memory Tools Module - Long-term memory search for conversation context
"""

from typing import Dict, Any, List
from fastmcp import FastMCP
from pydantic import Field

from backend.memory import MemoryManager
from backend.nagisa_mcp.utils.tool_result import ToolResult

def register_memory_tools(mcp: FastMCP):
    """Register memory search tools with proper tags synchronization."""
    
    # Initialize MemoryManager
    memory_manager = MemoryManager()
    
    common_kwargs = dict(
        tags={"memory", "search", "semantic", "conversation", "history"}, 
        annotations={"category": "memory", "tags": ["memory", "search", "semantic", "conversation", "history"]}
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
    
    @mcp.tool(**common_kwargs)
    def search_memory(
        query: str = Field(..., description="Search query for semantic memory retrieval (e.g., 'user preferences', 'project deadlines')."),
        max_results: int = Field(5, ge=1, le=20, description="Maximum number of memory results to return (1-20).")
    ) -> Dict[str, Any]:
        """Search conversation memory using semantic similarity for context retrieval.
        
        Searches long-term conversation memory database and returns relevant historical context
        with relevance scoring. Supports natural language queries for flexible memory access.
        """
        try:
            if not query or not query.strip():
                return _error("Search query cannot be empty")
            
            # Search memories using semantic similarity
            memories = memory_manager.search_memories(
                query=query,
                user_id="default",
                n_results=max_results
            )
            
            # Format memories for LLM consumption
            formatted_memories = []
            for memory in memories:
                relevance_score = 1 - memory["distance"] if memory.get("distance") is not None else 0.0
                
                formatted_memory = {
                    "content": memory["content"],
                    "relevance_score": round(relevance_score, 3),
                    "timestamp": memory["metadata"].get("timestamp"),
                    "conversation_id": memory["metadata"].get("conversation_id"),
                    "type": memory["metadata"].get("type", "general")
                }
                formatted_memories.append(formatted_memory)
            
            # Build structured response
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "search_memory",
                    "query": query,
                    "max_results": max_results,
                    "timestamp": timestamp
                },
                "result": {
                    "memories": formatted_memories,
                    "total_found": len(formatted_memories),
                    "search_limited": len(formatted_memories) >= max_results
                },
                "summary": {
                    "operation_type": "search_memory",
                    "success": True
                }
            }
            
            if formatted_memories:
                message = f"Found {len(formatted_memories)} relevant memories for '{query}'"
                high_relevance = [m for m in formatted_memories if m["relevance_score"] > 0.7]
                if high_relevance:
                    message += f" ({len(high_relevance)} highly relevant)"
            else:
                message = f"No memories found for '{query}'"
            
            return _success(
                message,
                llm_content,
                memories=formatted_memories,
                total_found=len(formatted_memories),
                query=query
            )
            
        except Exception as e:
            return _error(f"Failed to search memories: {str(e)}") 