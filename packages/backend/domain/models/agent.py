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
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """
    Configuration-driven agent definition.

    This model captures all aspects of an agent's behavior through configuration
    rather than hardcoding, following the design pattern from Gemini-CLI.

    Attributes:
        name: Unique identifier (e.g., "nagisa_main", "pfc_explorer")
        display_name: Human-readable name for UI display
        description: Functional description of the agent

        system_prompt: System prompt template with ${variable} placeholders
        initial_messages: Few-shot examples for the agent

        tool_profile: Profile name from ToolProfileManager

        max_iterations: Maximum tool call rounds before termination
        timeout_seconds: Execution timeout

        output_schema: Optional Pydantic model for structured output validation

        streaming_enabled: Whether to use streaming LLM calls
        inject_project_docs: Whether to inject CLAUDE.md and project context
        enable_memory: Whether to use long-term memory system
        enable_status_monitor: Whether to emit status events

    Example:
        PFC_EXPLORER = AgentDefinition(
            name="pfc_explorer",
            display_name="PFC Explorer",
            description="PFC documentation query and syntax validation agent",
            system_prompt="You are a PFC expert. Task: ${objective}",
            tool_profile="pfc",
            max_iterations=10,
            streaming_enabled=False,
        )
    """

    # === Identity ===
    name: str = Field(
        description="Unique identifier for the agent"
    )
    display_name: str = Field(
        description="Human-readable display name"
    )
    description: str = Field(
        description="Functional description of what this agent does"
    )

    # === Prompt Configuration ===
    system_prompt: str = Field(
        description="System prompt template (supports ${variable} placeholders)"
    )
    initial_messages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Few-shot example messages"
    )

    # === Tool Configuration ===
    tool_profile: str = Field(
        description="Tool profile name from ToolProfileManager"
    )

    # === Execution Constraints ===
    max_iterations: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum tool call iterations"
    )
    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Execution timeout in seconds"
    )

    # === Output Configuration ===
    output_schema_name: Optional[str] = Field(
        default=None,
        description="Name of the Pydantic model for output validation (resolved at runtime)"
    )

    # === Streaming Configuration ===
    streaming_enabled: bool = Field(
        default=True,
        description="Whether to use streaming LLM calls (main agent: True, subagent: False)"
    )

    # === Context Configuration ===
    inject_project_docs: bool = Field(
        default=True,
        description="Whether to inject CLAUDE.md and project documentation"
    )
    enable_memory: bool = Field(
        default=False,
        description="Whether to enable long-term memory (subagents typically disable)"
    )
    enable_status_monitor: bool = Field(
        default=True,
        description="Whether to emit status events for progress tracking"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "pfc_explorer",
                    "display_name": "PFC Explorer",
                    "description": "PFC documentation query agent",
                    "system_prompt": "You are a PFC expert. Task: ${objective}",
                    "tool_profile": "pfc",
                    "max_iterations": 10,
                    "timeout_seconds": 120,
                    "streaming_enabled": False,
                }
            ]
        }


class AgentResult(BaseModel):
    """
    Result of agent execution.

    Captures the outcome of an agent's execution cycle, including
    success/failure status, human-readable summary, and optional
    structured data.

    Attributes:
        status: Execution outcome status
        summary: Human-readable summary of what happened
        data: Structured data from the agent (if output_schema was used)
        raw_response: Raw LLM response text (when no schema validation)
        iterations_used: Number of tool call iterations used
        execution_time_seconds: Total execution time

    Example:
        AgentResult(
            status="success",
            summary="Found 3 relevant PFC commands for ball creation",
            data={"commands": [...], "examples": [...]},
            iterations_used=4,
            execution_time_seconds=12.5
        )
    """

    status: Literal["success", "error", "timeout", "max_iterations", "aborted"] = Field(
        description="Execution outcome status"
    )
    summary: str = Field(
        description="Human-readable summary of the result"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured data from validated output"
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw LLM response when no schema validation"
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

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "success",
                    "summary": "Task completed successfully",
                    "data": {"result": "validated data"},
                    "iterations_used": 3,
                    "execution_time_seconds": 8.5
                },
                {
                    "status": "timeout",
                    "summary": "Agent timed out after 120 seconds",
                    "iterations_used": 5,
                    "execution_time_seconds": 120.0
                }
            ]
        }


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
