"""
Memory context models for the enhanced memory infrastructure.

This module defines the data structures and context management
for the aiNagisa memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class MemoryType(str, Enum):
    """Types of memories with different persistence and importance."""
    FACT = "fact"  # Long-term facts about the user
    PREFERENCE = "preference"  # User preferences and habits
    CONTEXT = "context"  # Session or conversation context
    EVENT = "event"  # Specific events or incidents


class MemoryTier(str, Enum):
    """Memory tier classification for hierarchical storage."""
    LONG_TERM = "long_term"  # 30+ days retention
    MEDIUM_TERM = "medium_term"  # 7-30 days retention
    SHORT_TERM = "short_term"  # 1-7 days retention
    WORKING = "working"  # Current session only


@dataclass
class EnhancedMemory:
    """
    Enhanced memory model with metadata and lifecycle management.
    
    This replaces the simple string-based memory with a rich
    structured format that supports time-awareness, confidence
    scoring, and memory hierarchy.
    """
    content: str
    embedding: List[float]
    timestamp: datetime
    memory_type: MemoryType
    memory_tier: MemoryTier = MemoryTier.SHORT_TERM
    confidence: float = 0.8
    expires_at: Optional[datetime] = None
    source: str = "conversation"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Additional tracking fields
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary for storage."""
        return {
            "content": self.content,
            "embedding": self.embedding,
            "timestamp": self.timestamp.isoformat(),
            "memory_type": self.memory_type.value,
            "memory_tier": self.memory_tier.value,
            "confidence": self.confidence,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "source": self.source,
            "metadata": self.metadata,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "relevance_score": self.relevance_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedMemory":
        """Create memory from dictionary."""
        return cls(
            content=data["content"],
            embedding=data.get("embedding", []),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            memory_type=MemoryType(data["memory_type"]),
            memory_tier=MemoryTier(data.get("memory_tier", MemoryTier.SHORT_TERM.value)),
            confidence=data.get("confidence", 0.8),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            source=data.get("source", "conversation"),
            metadata=data.get("metadata", {}),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            relevance_score=data.get("relevance_score", 0.0)
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
    memory_types: Optional[List[MemoryType]] = None
    relevance_threshold: float = 0.5
    
    # Results
    memories: List[EnhancedMemory] = field(default_factory=list)
    injection_time_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    
    def filter_by_relevance(self) -> List[EnhancedMemory]:
        """Filter memories by relevance threshold."""
        return [m for m in self.memories if m.relevance_score >= self.relevance_threshold]
    
    def get_high_confidence_memories(self, min_confidence: float = 0.7) -> List[EnhancedMemory]:
        """Get memories with high confidence scores."""
        return [m for m in self.memories if m.confidence >= min_confidence]
    
    def format_for_injection(self) -> str:
        """
        Format memories for LLM context injection.
        
        Returns a formatted string ready to be inserted as a system message.
        """
        if not self.memories:
            return ""
        
        formatted_lines = ["[Memory Context]"]
        
        # Group memories by type for better organization
        memories_by_type = {}
        for memory in self.filter_by_relevance():
            memory_type = memory.memory_type.value
            if memory_type not in memories_by_type:
                memories_by_type[memory_type] = []
            memories_by_type[memory_type].append(memory)
        
        # Format each type section
        for memory_type, type_memories in memories_by_type.items():
            formatted_lines.append(f"\n{memory_type.upper()}:")
            for memory in type_memories:
                confidence_marker = "⭐" if memory.confidence > 0.8 else ""
                formatted_lines.append(f"- {memory.content} {confidence_marker}")
        
        return "\n".join(formatted_lines)


@dataclass
class MemoryInjectionResult:
    """Result of memory injection operation."""
    success: bool
    injected_count: int
    error: Optional[str] = None
    context_tokens: Optional[int] = None
    formatted_context: Optional[str] = None