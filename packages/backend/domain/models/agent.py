"""
Agent domain models for the SubAgent abstraction system.

This module defines the core data structures for configuration-driven
agent execution, enabling both main Agent and SubAgent to share the
same execution framework.

Key models:
    - AgentDefinition: Complete agent configuration
    - AgentResult: Execution result with status and data
    - AgentActivity: Activity events for progress tracking
"""

import time
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from backend.domain.models.messages import BaseMessage


class AgentDefinition(BaseModel):
    """
    Configuration-driven agent definition (simplified).

    The agent's system prompt is loaded from config/prompts/{name}.md,
    reusing the existing prompt infrastructure with tool schemas and
    environment info injection.

    Attributes:
        name: Unique identifier, also used as prompt profile name
              (loads from config/prompts/{name}.md)
        display_name: Human-readable name for UI display
        description: Functional description of the agent
        tool_profile: Profile name from ToolProfileManager
        max_iterations: Maximum tool call rounds before termination
        streaming_enabled: Whether to use streaming LLM calls
        enable_memory: Whether to use long-term memory system

    Example:
        PFC_EXPLORER = AgentDefinition(
            name="pfc_explorer",        # loads config/prompts/pfc_explorer.md
            display_name="PFC Explorer",
            description="PFC documentation query and syntax validation agent",
            tool_profile="pfc",         # uses PFC tool set
            max_iterations=10,
            streaming_enabled=False,
            enable_memory=False,
        )
    """

    # === Identity (name doubles as prompt profile) ===
    name: str = Field(
        description="Unique identifier, also used as prompt profile (loads {name}.md)"
    )
    display_name: str = Field(
        description="Human-readable display name"
    )
    description: str = Field(
        description="Functional description of what this agent does"
    )

    # === Tool Configuration ===
    tool_profile: str = Field(
        description="Tool profile name from ToolProfileManager"
    )

    # === Execution Constraints ===
    max_iterations: int = Field(
        default=64,
        ge=1,
        le=100,
        description="Maximum tool call iterations"
    )

    # === Streaming Configuration ===
    streaming_enabled: bool = Field(
        default=True,
        description="Whether to use streaming LLM calls (main agent: True, subagent: False)"
    )

    # === Context Configuration ===
    enable_memory: bool = Field(
        default=True,
        description="Whether to enable long-term memory (subagents typically disable)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "pfc_explorer",
                    "display_name": "PFC Explorer",
                    "description": "PFC documentation query agent",
                    "tool_profile": "pfc",
                    "max_iterations": 10,
                    "streaming_enabled": False,
                    "enable_memory": False,
                }
            ]
        }


class AgentResult(BaseModel):
    """
    Unified result of agent execution.

    Supports both MainAgent (streaming) and SubAgent (non-streaming) scenarios
    with a single return type for consistent handling.

    Attributes:
        status: Execution outcome status
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
    """

    # === Status ===
    status: Literal["success", "error", "max_iterations", "aborted"] = Field(
        description="Execution outcome status"
    )

    # === Response Content ===
    message: Optional[Any] = Field(
        default=None,
        description="Structured response message (BaseMessage)"
    )

    # === Streaming Metadata ===
    message_id: Optional[str] = Field(
        default=None,
        description="Streaming message ID for WebSocket updates (MainAgent only)"
    )

    # === Execution Metadata ===
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
        """
        if self.message:
            from backend.domain.models.message_factory import extract_text_from_message
            return extract_text_from_message(self.message)
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

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "agent_name": "pfc_explorer",
                    "event_type": "tool_call_start",
                    "data": {"tool": "pfc_query_command", "args": {"command": "ball"}},
                    "timestamp": 1701500000.0
                },
                {
                    "agent_name": "pfc_explorer",
                    "event_type": "completed",
                    "data": {"status": "success", "iterations": 3},
                    "timestamp": 1701500015.0
                }
            ]
        }
