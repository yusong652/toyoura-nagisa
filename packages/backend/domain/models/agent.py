"""
Agent domain models for the agent execution system.

This module defines the core data structures for agent execution results
and activity tracking.

Key models:
    - AgentResult: Execution result with status and data
    - AgentActivity: Activity events for progress tracking

Note: Agent configuration is now defined in agent_profiles.py
(ProfileConfig for MainAgent, SubAgentConfig for SubAgent).
"""

import time
from typing import Any, Dict, Literal, Optional

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

    status: Literal["success", "error", "max_iterations", "aborted", "empty_response"] = Field(
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


class AgentActivity(BaseModel):
    """
    Agent activity event for progress tracking.

    Emitted during agent execution to allow parent agents and
    frontends to monitor progress in real-time.

    Attributes:
        agent_name: Name of the agent emitting the event
        event_type: Type of activity event
        data: Event-specific data
        timestamp: Unix timestamp of the event

    Event Types:
        - "started": Agent execution started
        - "thinking": Agent is processing/reasoning
        - "tool_call_start": Starting a tool call
        - "tool_call_end": Tool call completed
        - "llm_response": LLM response received
        - "completed": Agent execution finished
        - "error": Error occurred

    Example:
        AgentActivity(
            agent_name="pfc_explorer",
            event_type="tool_call_start",
            data={"tool": "pfc_query_command", "args": {"command": "ball create"}}
        )
    """

    agent_name: str = Field(
        description="Name of the agent emitting this event"
    )

    event_type: Literal[
        "started",
        "thinking",
        "tool_call_start",
        "tool_call_end",
        "llm_response",
        "completed",
        "error"
    ] = Field(
        description="Type of activity event"
    )

    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data payload"
    )

    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when event occurred"
    )
