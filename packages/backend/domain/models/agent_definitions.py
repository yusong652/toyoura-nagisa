"""
Predefined agent configurations.

This module contains all built-in agent definitions. New agents
can be added here or registered at runtime via AgentRegistry.
"""

from typing import Dict

from backend.domain.models.agent import AgentDefinition


# === PFC Explorer SubAgent ===
PFC_EXPLORER = AgentDefinition(
    name="pfc_explorer",
    display_name="PFC Explorer",
    description="PFC documentation query and syntax validation agent",
    system_prompt="""You are the PFC Explorer Agent, a specialized subagent for querying PFC documentation and validating syntax.

## Your Task
${objective}

## Context
${context}

## Workflow
1. Use pfc_query_python_api to find Python SDK usage (prefer this first)
2. Use pfc_query_command to find command syntax and model properties
3. If validation is needed, write a minimal test script and execute it
4. Return verified, working code

## Rules
- Work autonomously, do not ask for user input
- Only report validated syntax
- Be concise and focused on the task
- If you cannot find the information, say so clearly""",
    tool_profile="pfc",
    max_iterations=10,
    timeout_seconds=120,
    streaming_enabled=False,
    inject_project_docs=False,
    enable_memory=False,
    enable_status_monitor=True,
)


# === Agent Registry ===
AGENT_DEFINITIONS: Dict[str, AgentDefinition] = {
    "pfc_explorer": PFC_EXPLORER,
}
