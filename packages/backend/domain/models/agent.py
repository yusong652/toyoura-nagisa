"""
Agent domain models for the agent execution system.

This module defines the core data structures for agent execution results.

Key models:
    - AgentResult: Execution result with status and data

Note: Agent configuration is now defined in agent_profiles.py
(ProfileConfig for MainAgent, SubAgentConfig for SubAgent).
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """
    Unified result of agent execution.

    Supports both MainAgent (streaming) and SubAgent (non-streaming) scenarios
    with a single return type for consistent handling.

    Attributes:
        status: Execution outcome status
            - success: Completed with meaningful response
            - error: Execution failed with error
            - max_iterations: Reached iteration limit
            - aborted: Execution was aborted
            - empty_response: Completed but returned empty/whitespace-only content
            - user_rejected: User rejected a tool execution (SubAgent only)
        message: Structured response message (BaseMessage)
        message_id: Streaming message ID for WebSocket updates (MainAgent only)
        iterations_used: Number of tool call iterations used
        execution_time_seconds: Total execution time

    Usage:
        # MainAgent scenario
        result = await agent.execute(instruction, session_id=session_id)
        if result.status == "success" and result.message:
            await process_content_pipeline(result.message, session_id, result.message_id)

        # SubAgent scenario
        result = await agent.execute(instruction)
        if result.status == "success":
            response_text = result.text  # Convenience property
        elif result.status == "empty_response":
            # SubAgent completed but returned no content - may need prompt adjustment
            pass
    """

    status: Literal["success", "error", "max_iterations", "aborted", "empty_response", "user_rejected"] = Field(
        description="Execution outcome status"
    )

    message: Optional[Any] = Field(
        default=None,
        description="Structured response message (BaseMessage)"
    )

    message_id: Optional[str] = Field(
        default=None,
        description="Streaming message ID for WebSocket updates (MainAgent only)"
    )

    iterations_used: int = Field(
        default=0,
        ge=0,
        description="Number of tool call iterations used"
    )

    execution_time_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Total execution time in seconds"
    )

    model_config = {"arbitrary_types_allowed": True}

    @property
    def text(self) -> str:
        """
        Convenience property to get plain text response.

        Uses existing infrastructure from message_factory.
        Strips whitespace to handle empty responses from some LLM APIs
        (e.g., Zhipu returns "\n" as default empty response).
        """
        if self.message:
            from backend.domain.models.message_factory import extract_text_from_message
            text = extract_text_from_message(self.message)
            # Strip whitespace - empty/whitespace-only responses have no meaning
            return text.strip() if text else ""
        return ""
