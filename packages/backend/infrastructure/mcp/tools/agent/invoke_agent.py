"""invoke_agent tool - delegate tasks to specialized SubAgents.

This tool enables MainAgent to launch SubAgents for specific tasks,
following the same pattern as Claude Code's Task tool.

Design principles:
- SubAgents are stateless (no session persistence)
- MainAgent controls the prompt content entirely
- SubAgent returns a final report as plain text
"""

import logging
from typing import Any, Dict, Literal
from pydantic import Field
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

logger = logging.getLogger(__name__)

__all__ = ["invoke_agent", "register_invoke_agent_tool"]


# Available SubAgent types (matches SubAgentConfig names in agent_profiles.py)
AVAILABLE_SUBAGENTS = {
    "pfc_explorer": "PFC documentation query agent (read-only)",
}


async def invoke_agent(
    context: Context,
    description: str = Field(
        ...,
        description="A short (3-5 word) description of the task"
    ),
    prompt: str = Field(
        ...,
        description="The task for the agent to perform"
    ),
    subagent_type: Literal["pfc_explorer"] = Field(
        ...,
        description="The type of specialized agent to use for this task"
    ),
) -> Dict[str, Any]:
    """Launch a new agent to handle complex, multi-step tasks autonomously.

The invoke_agent tool launches specialized agents (subprocesses) that autonomously handle complex tasks. Each agent type has specific capabilities and tools available to it.

Available agent types and the tools they have access to:
- pfc_explorer: PFC documentation query agent (read-only). Use this when you need to query PFC command syntax, find Python API usage examples, or search workspace files for context. This agent cannot execute scripts or modify files. (Tools: read, glob, grep, bash, bash_output, pfc_browse_commands, pfc_browse_python_api, pfc_query_command, pfc_query_python_api, pfc_browse_contact_models, web_search, todo_write)

When using the invoke_agent tool, you must specify a subagent_type parameter to select which agent type to use.

Usage notes:
- Launch agents when the task requires specialized domain knowledge
- The agent's outputs should generally be trusted
- Clearly tell the agent whether you expect it to write code or just to do research
- Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
    """
    session_id = context.client_id
    if not session_id:
        raise RuntimeError("Session ID not found in context")

    # Validate agent type
    if subagent_type not in AVAILABLE_SUBAGENTS:
        return error_response(
            f"Unknown subagent type: {subagent_type}. Available: {', '.join(AVAILABLE_SUBAGENTS.keys())}",
            available_subagents=list(AVAILABLE_SUBAGENTS.keys())
        )

    try:
        # Import here to avoid circular dependencies
        from backend.domain.models.agent_profiles import get_subagent_config
        from backend.application.services.agent_service import AgentService
        from backend.shared.utils.app_context import get_secondary_llm_client

        # Get SubAgent configuration
        config = get_subagent_config(subagent_type)

        # Create AgentService with secondary LLM client (lighter model to reduce RPM)
        llm_client = get_secondary_llm_client()
        agent_service = AgentService(llm_client)

        # Get tool_call_id from request_context.meta (passed by tool_manager)
        # This is the LLM-generated tool_call_id for frontend association
        parent_tool_call_id = ""
        req_ctx = context.request_context
        if req_ctx and hasattr(req_ctx, 'meta') and req_ctx.meta:
            parent_tool_call_id = getattr(req_ctx.meta, 'tool_call_id', "") or ""

        # Execute SubAgent (pass MainAgent's session_id for confirmation routing)
        logger.info(f"[invoke_agent] Starting SubAgent '{subagent_type}' ({description}) for session {session_id[:8]}")
        result = await agent_service.run_subagent(
            config=config,
            instruction=prompt,
            notification_session_id=session_id,  # Route confirmations to MainAgent's WebSocket
            parent_tool_call_id=parent_tool_call_id,  # For frontend to associate SubAgent tools
        )

        # Format result based on execution status (domain-level status)
        if result.status == "success":
            return success_response(
                message=f"SubAgent '{config.display_name}' completed successfully",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": result.text
                    }]
                },
                subagent_type=subagent_type,
                iterations_used=result.iterations_used,
                execution_time_seconds=result.execution_time_seconds,
            )
        elif result.status == "user_rejected":
            # SubAgent's tool was rejected by user - propagate rejection to MainAgent
            from backend.shared.exceptions import UserRejectionInterruption

            # Return error response first (for tool result)
            error_result = error_response(
                f"SubAgent '{config.display_name}' was rejected by user. "
                f"Details:\n\n{result.text}",
                subagent_type=subagent_type,
                status="user_rejected",
                execution_time_seconds=result.execution_time_seconds,
            )
            error_result["user_rejected"] = True

            # Raise interruption to stop MainAgent execution
            # The rejection context has already been saved by SubAgent
            raise UserRejectionInterruption(
                session_id=session_id,
                rejected_tools=[f"invoke_agent:{subagent_type}"]
            )
        elif result.status == "empty_response":
            # SubAgent completed but returned empty/whitespace-only content
            return error_response(
                f"SubAgent '{config.display_name}' completed but returned empty response. "
                f"Please retry with a more explicit prompt that asks the SubAgent to "
                f"summarize findings or provide a detailed response.",
                subagent_type=subagent_type,
                iterations_used=result.iterations_used,
                execution_time_seconds=result.execution_time_seconds,
            )
        elif result.status == "max_iterations":
            return error_response(
                f"SubAgent '{config.display_name}' reached iteration limit ({config.max_iterations}). "
                f"The task may be incomplete. Partial result:\n\n{result.text}",
                subagent_type=subagent_type,
                iterations_used=result.iterations_used,
                execution_time_seconds=result.execution_time_seconds,
            )
        else:
            # error or aborted
            return error_response(
                f"SubAgent '{config.display_name}' failed with status: {result.status}. "
                f"Error details:\n\n{result.text}",
                subagent_type=subagent_type,
                status=result.status,
                execution_time_seconds=result.execution_time_seconds,
            )

    except KeyError as e:
        logger.error(f"SubAgent configuration not found: {e}")
        return error_response(
            f"SubAgent '{subagent_type}' is not configured. Please check SUBAGENT_CONFIGS in agent_profiles.py",
            subagent_type=subagent_type
        )
    except Exception as e:
        logger.error(f"SubAgent execution failed: {e}", exc_info=True)
        return error_response(
            f"SubAgent execution failed: {str(e)}",
            subagent_type=subagent_type
        )


def register_invoke_agent_tool(mcp: FastMCP):
    """Register the invoke_agent tool with metadata."""
    mcp.tool(
        tags={"agent", "subagent", "delegation", "task"},
        annotations={
            "category": "agent",
            "tags": ["agent", "subagent", "delegation", "task"],
            "primary_use": "Delegate specialized tasks to SubAgents",
            "prompt_optimization": "Claude Code Task tool compatible interface",
        }
    )(invoke_agent)
