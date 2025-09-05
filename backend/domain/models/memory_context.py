"""
Memory context models for the enhanced memory infrastructure.

This module defines the data structures and context management
for the aiNagisa memory system.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional




@dataclass
class EnhancedMemory:
    """
    Simplified memory model for Mem0 integration.
    
    Contains only the essential fields needed for memory injection and display.
    """
    content: str
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary for storage."""
        return {
            "content": self.content,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedMemory":
        """Create memory from dictionary."""
        return cls(
            content=data["content"],
            relevance_score=data.get("relevance_score", 0.0),
            metadata=data.get("metadata", {})
        )


@dataclass
class MemoryContext:
    """
    Context for memory operations including search and injection.
    
    This encapsulates the parameters and results of memory operations
    to provide a clean interface between layers.
    All memory searches are cross-session for comprehensive context.
    """
    query: str
    top_k: int = 5
    exclude_recent_minutes: int = 10
    relevance_threshold: float = 0.5
    
    # Results
    memories: List[EnhancedMemory] = field(default_factory=list)
    injection_time_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    
    def filter_by_relevance(self) -> List[EnhancedMemory]:
        """Filter memories by relevance threshold."""
        if not self.memories:
            return []
        return [m for m in self.memories if m.relevance_score >= self.relevance_threshold]
    
    def get_high_relevance_memories(self, min_relevance: float = 0.7) -> List[EnhancedMemory]:
        """Get memories with high relevance scores."""
        if not self.memories:
            return []
        return [m for m in self.memories if m.relevance_score >= min_relevance]
    
    def format_for_injection(self) -> str:
        """
        Format memories for LLM context injection.
        
        Returns a formatted string ready to be inserted as a system message.
        """
        if not self.memories:
            return ""
        
        formatted_lines = ["[Memory Context]"]
        
        # Format relevant memories
        for memory in self.filter_by_relevance():
            relevance_marker = "⭐" if memory.relevance_score > 0.8 else ""
            formatted_lines.append(f"- {memory.content} {relevance_marker}")
        
        return "\n".join(formatted_lines)


@dataclass
class MemoryInjectionResult:
    """Result of memory injection operation."""
    success: bool
    injected_count: int
    error: Optional[str] = None
    context_tokens: Optional[int] = None
    formatted_context: Optional[str] = None