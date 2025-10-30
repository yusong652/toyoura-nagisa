"""
Streaming data models for real-time LLM response processing.

This module defines standardized data structures for streaming chunks
that are yielded during LLM API streaming calls.
"""

from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class StreamingChunk(BaseModel):
    """
    Standardized streaming chunk data structure.

    This unified format is used across all LLM providers to represent
    individual pieces of streaming responses, enabling consistent handling
    of thinking content, text, and function calls.

    Attributes:
        chunk_type: Type of content in this chunk
        content: The actual text content of the chunk
        metadata: Additional provider-specific or context-specific data
        thought_signature: Optional cryptographic signature for thinking chains (Gemini)
        function_call: Optional function call details when chunk_type is "function_call"

    Example:
        # Thinking chunk
        StreamingChunk(
            chunk_type="thinking",
            content="Let me analyze this problem step by step...",
            metadata={"thought": True}
        )

        # Text chunk
        StreamingChunk(
            chunk_type="text",
            content="The answer is 42.",
            metadata={}
        )

        # Function call chunk
        StreamingChunk(
            chunk_type="function_call",
            content="calculate",
            metadata={"args": {"expression": "2 + 2"}},
            function_call={"name": "calculate", "args": {"expression": "2 + 2"}}
        )
    """

    chunk_type: Literal["thinking", "text", "function_call"] = Field(
        description="Type of streaming chunk content"
    )

    content: str = Field(
        description="The text content of this chunk"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about this chunk"
    )

    # Provider-specific fields (optional)
    thought_signature: Optional[bytes] = Field(
        default=None,
        description="Cryptographic signature for thinking chains (Gemini-specific)"
    )

    function_call: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Function call details when chunk_type is 'function_call'"
    )

    class Config:
        """Pydantic model configuration"""
        json_schema_extra = {
            "examples": [
                {
                    "chunk_type": "thinking",
                    "content": "Analyzing the problem...",
                    "metadata": {"thought": True, "has_signature": False}
                },
                {
                    "chunk_type": "text",
                    "content": "Here's the solution:",
                    "metadata": {}
                },
                {
                    "chunk_type": "function_call",
                    "content": "get_weather",
                    "metadata": {"args": {"city": "Tokyo"}},
                    "function_call": {"name": "get_weather", "args": {"city": "Tokyo"}}
                }
            ]
        }
