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


# Available SubAgent types (matches AgentConfig names in agent_profiles.py)
AVAILABLE_SUBAGENTS = {
    "pfc_explorer": "Tama - PFC documentation query agent (read-only)",
    "pfc_diagnostic": "Hoshi - PFC multimodal diagnostic agent (visual analysis)",
}


async def invoke_agent(
    context: Context,
    subagent_type: Literal["pfc_explorer", "pfc_diagnostic"] = Field(
        ..., description="The type of specialized agent to use for this task"
    ),
    description: str = Field(..., description="A short (3-5 word) description of the task"),
    prompt: str = Field(..., description="The task for the agent to perform"),
) -> Dict[str, Any]:
    """Launch a new agent to handle complex, multi-step tasks autonomously.

    The invoke_agent tool launches specialized agents (subprocesses) that autonomously handle complex tasks. Each agent type has specific capabilities and tools available to it.

    Available agent types:
    - pfc_explorer: PFC documentation query agent (read-only). Use for multi-step doc exploration, finding command syntax, Python API usage, or searching workspace files. Prompt tip: specify if you need command syntax, Python API, or both. (Tools: read, glob, grep, bash, bash_output, pfc_browse_commands, pfc_browse_python_api, pfc_query_command, pfc_query_python_api, pfc_browse_reference, web_search, todo_write)
    - pfc_diagnostic: PFC multimodal diagnostic agent. Use for visual diagnosis of simulation issues by capturing and analyzing screenshots from multiple angles and coloring modes. Prompt tip: include paths to existing images or specify output directory. (Tools: pfc_capture_plot, read, pfc_check_task_status, pfc_list_tasks, pfc_query_command, pfc_query_python_api, glob, grep, bash, bash_output, todo_write)

    When NOT to use:
    - Single doc query with known path: use pfc_browse_commands or pfc_browse_python_api directly
    - Quick visual capture with known settings: use pfc_capture_plot directly
    - Simple file reading: use read tool directly

    Usage notes:
    - Launch agents when the task requires multi-step exploration or specialized diagnosis
    - The agent's outputs should generally be trusted
    - Each invocation is stateless and returns a single final report
    - The result returned by the agent is not visible to the user. Summarize the result in your response.
    - Be specific about what information to return (syntax, examples, limitations, alternatives)
    - Include context: what you observed, what you suspect, what needs investigation
    """
    # Architecture guarantee: tool_manager.py always injects _meta.client_id
    session_id = context.client_id
    if session_id is None:
        return error_response("Missing session ID for invoke_agent")
    session_id_value: str = str(session_id)

    # Validate agent type
    if subagent_type not in AVAILABLE_SUBAGENTS:
        return error_response(
            f"Unknown subagent type: {subagent_type}. Available: {', '.join(AVAILABLE_SUBAGENTS.keys())}",
            available_subagents=list(AVAILABLE_SUBAGENTS.keys()),
        )

    try:
        # Import here to avoid circular dependencies
        from backend.domain.models.agent_profiles import get_subagent_config
        from backend.application.services.agent.service import AgentService
        from backend.shared.utils.app_context import get_secondary_llm_client, get_llm_factory
        from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
        from backend.infrastructure.storage.session_manager import get_session_llm_config

        # Get SubAgent configuration
        config = get_subagent_config(subagent_type)

        # Create AgentService with secondary LLM client (lighter model to reduce RPM)
        llm_client = None
        session_llm_config = get_session_llm_config(session_id_value)
        default_llm_config = get_default_llm_config()

        provider = None
        secondary_model = None
        if session_llm_config:
            provider = session_llm_config.get("provider")
            secondary_model = session_llm_config.get("secondary_model")

        if not secondary_model and default_llm_config:
            provider = provider or default_llm_config.get("provider")
            secondary_model = default_llm_config.get("secondary_model")

        if provider and not secondary_model:
            if provider == "google":
                from backend.infrastructure.llm.providers.google.config import GoogleConfig

                secondary_model = GoogleConfig().secondary_model
            elif provider == "anthropic":
                from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig

                secondary_model = AnthropicConfig().secondary_model
            elif provider in ("openai", "gpt"):
                from backend.infrastructure.llm.providers.openai.config import OpenAIConfig

                secondary_model = OpenAIConfig().secondary_model
            elif provider == "moonshot":
                from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig

                secondary_model = MoonshotConfig().secondary_model
            elif provider == "zhipu":
                from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig

                secondary_model = ZhipuConfig().secondary_model
            elif provider == "openrouter":
                from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig

                secondary_model = OpenRouterConfig().secondary_model

        if provider and secondary_model:
            llm_factory = get_llm_factory()
            llm_client = llm_factory.create_client_with_config(
                provider=provider,
                model=secondary_model,
            )
        else:
            llm_client = get_secondary_llm_client()
        agent_service = AgentService(llm_client)

        # Get tool_call_id from request_context.meta (passed by tool_manager)
        # This is the LLM-generated tool_call_id for frontend association
        parent_tool_call_id = ""
        req_ctx = context.request_context
        if req_ctx and hasattr(req_ctx, "meta") and req_ctx.meta:
            parent_tool_call_id = getattr(req_ctx.meta, "tool_call_id", "") or ""

        result = await agent_service.run_subagent(
            config=config,
            instruction=prompt,
            notification_session_id=session_id_value,  # Route confirmations to MainAgent's WebSocket
            parent_tool_call_id=parent_tool_call_id,  # For frontend to associate SubAgent tools
        )

        # Format result based on execution status (domain-level status)
        if result.status == "success":
            return success_response(
                message=f"SubAgent '{config.display_name}' completed successfully",
                llm_content={"parts": [{"type": "text", "text": result.text}]},
                subagent_type=subagent_type,
                iterations_used=result.iterations_used,
                execution_time_seconds=result.execution_time_seconds,
            )
        elif result.status == "user_rejected":
            # SubAgent's tool was rejected by user - return special marker for MainAgent
            # Note: Cannot raise exception here as MCP tools run in separate process
            # The marker will be detected by tool_manager and converted to exception
            # Rejection context already saved by SubAgent for next message injection
            response = error_response(
                f"SubAgent '{config.display_name}' was rejected by user.",
                subagent_type=subagent_type,
                execution_time_seconds=result.execution_time_seconds,
            )
            response["_subagent_user_rejected"] = True  # Special marker for tool_manager
            response["_rejected_tools"] = [f"invoke_agent:{subagent_type}"]
            return response
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
            subagent_type=subagent_type,
        )
    except Exception as e:
        logger.error(f"SubAgent execution failed: {e}", exc_info=True)
        return error_response(f"SubAgent execution failed: {str(e)}", subagent_type=subagent_type)


def register_invoke_agent_tool(mcp: FastMCP):
    """Register the invoke_agent tool with metadata."""
    mcp.tool(
        tags={"agent", "subagent", "delegation", "task"},
        annotations={
            "category": "agent",
            "tags": ["agent", "subagent", "delegation", "task"],
            "primary_use": "Delegate specialized tasks to SubAgents",
            "prompt_optimization": "Claude Code Task tool compatible interface",
        },
    )(invoke_agent)
