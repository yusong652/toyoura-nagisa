"""
Agent - First-class citizen with active behavior.

This module provides the Agent class that encapsulates both
configuration (AgentDefinition) and behavior (run/stream methods).
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.domain.models.agent import AgentActivity, AgentDefinition, AgentResult
from backend.domain.models.messages import UserMessage
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.services.conversation.tool_executor import ToolExecutor
from backend.application.services.message_service import MessageService


class _ToolExecutionContext:
    """
    Minimal context adapter for Agent tool execution.

    Provides the interface expected by ToolExecutor.
    This is an internal implementation detail.
    """

    def __init__(self, agent_profile: str):
        self.agent_profile = agent_profile

    async def add_tool_result(
        self,
        tool_call_id: str,  # noqa: ARG002
        tool_name: str,  # noqa: ARG002
        result: Dict[str, Any],  # noqa: ARG002
        inject_reminders: bool = False  # noqa: ARG002
    ) -> None:
        """No-op - results handled by Agent internally."""
        pass


class Agent:
    """
    Agent with active behavior - first-class citizen in the system.

    An Agent encapsulates:
    - Configuration (AgentDefinition)
    - Behavior (run for non-streaming, stream for streaming)
    - State management (context, execution tracking)

    Usage:
        # Create agent instance
        explorer = Agent(PFC_EXPLORER, llm_client)

        # Execute task (non-streaming)
        result = await explorer.run({"objective": "Find ball syntax"})

        # Or with activity monitoring
        def on_activity(activity):
            print(f"[{activity.event_type}] {activity.data}")

        explorer = Agent(PFC_EXPLORER, llm_client, on_activity=on_activity)
        result = await explorer.run(inputs)
    """

    def __init__(
        self,
        definition: AgentDefinition,
        llm_client: LLMClientBase,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ):
        """
        Initialize Agent.

        Args:
            definition: Agent configuration (name, system_prompt, tools, limits)
            llm_client: LLM client for API calls
            on_activity: Optional callback for activity events
        """
        self.definition = definition
        self.llm_client = llm_client
        self.on_activity = on_activity

        # Execution state (reset on each run)
        self._execution_id: Optional[str] = None

    @property
    def name(self) -> str:
        """Agent name from definition."""
        return self.definition.name

    @property
    def display_name(self) -> str:
        """Agent display name from definition."""
        return self.definition.display_name

    async def run(
        self,
        inputs: Dict[str, str],
        abort_signal: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """
        Execute agent task (non-streaming mode).

        This is the primary method for SubAgents. The agent will:
        1. Build context from inputs
        2. Call LLM
        3. Execute tools if requested
        4. Repeat until done or limits reached

        Args:
            inputs: Task inputs (e.g., {"objective": "...", "context": "..."})
            abort_signal: Optional event to signal abort

        Returns:
            AgentResult with execution outcome
        """
        # Generate unique execution ID for this run
        self._execution_id = str(uuid.uuid4())[:8]

        start_time = time.time()
        iteration = 0

        self._emit_activity("started", {"inputs": inputs})

        try:
            # Setup context manager for this execution
            context_manager = self.llm_client.get_or_create_context_manager(
                self._execution_id
            )
            context_manager.agent_profile = self.definition.tool_profile
            context_manager.enable_memory = self.definition.enable_memory

            # Build initial user message from inputs (task from parent agent)
            initial_message = UserMessage(content=self._build_prompt_content(inputs))
            await context_manager.add_user_message(initial_message)

            # Get api_config using infrastructure layer
            messages, api_config = await self.llm_client._prepare_complete_context(
                session_id=self._execution_id,
                system_prompt=self.definition.system_prompt
            )

            # Execution loop
            while iteration < self.definition.max_iterations:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.definition.timeout_seconds:
                    return AgentResult(
                        status="timeout",
                        summary=f"Agent timed out after {self.definition.timeout_seconds}s",
                        iterations_used=iteration,
                        execution_time_seconds=elapsed,
                    )

                # Check abort signal
                if abort_signal and abort_signal.is_set():
                    return AgentResult(
                        status="aborted",
                        summary="Agent aborted by user",
                        iterations_used=iteration,
                        execution_time_seconds=time.time() - start_time,
                    )

                # Get fresh messages from context_manager
                messages = context_manager.get_working_contents()

                # LLM call
                self._emit_activity("thinking", {"iteration": iteration})
                response = await self.llm_client.call_api_with_context(
                    context_contents=messages,
                    api_config=api_config,
                )
                self._emit_activity("llm_response", {"iteration": iteration})

                # Extract response content and tool calls
                response_text, tool_calls = self._parse_response(response)

                # No tool calls = done
                if not tool_calls:
                    return AgentResult(
                        status="success",
                        summary=self._extract_summary(response_text),
                        raw_response=response_text,
                        iterations_used=iteration + 1,
                        execution_time_seconds=time.time() - start_time,
                    )

                # Add assistant response to context
                context_manager.add_response(response)

                # Execute tools and add results to context
                tool_results = await self._execute_tools(tool_calls, iteration)
                for tool_call, result in zip(tool_calls, tool_results):
                    if result is not None:
                        await context_manager.add_tool_result(
                            tool_call_id=tool_call.get("id", ""),
                            tool_name=tool_call.get("name", ""),
                            result=result,
                            inject_reminders=False
                        )

                iteration += 1

            # Max iterations reached
            return AgentResult(
                status="max_iterations",
                summary=f"Reached max iterations ({self.definition.max_iterations})",
                iterations_used=iteration,
                execution_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            self._emit_activity("error", {"error": str(e)})
            return AgentResult(
                status="error",
                summary=f"Agent error: {str(e)}",
                iterations_used=iteration,
                execution_time_seconds=time.time() - start_time,
            )

        finally:
            self._emit_activity("completed", {
                "iterations": iteration,
                "elapsed": time.time() - start_time,
            })

    # async def stream(self, inputs: Dict[str, str]) -> AsyncGenerator:
    #     """
    #     Execute agent task (streaming mode).
    #
    #     This will be implemented when we refactor ChatOrchestrator.
    #     For now, Main Agent continues to use ChatOrchestrator.
    #     """
    #     raise NotImplementedError("Streaming mode not yet implemented")

    def _build_prompt_content(self, inputs: Dict[str, str]) -> str:
        """
        Build prompt content from inputs for initial user message.

        Args:
            inputs: Task inputs

        Returns:
            Prompt string for the initial user message
        """
        if len(inputs) == 1:
            return str(list(inputs.values())[0])

        parts = []
        for key, value in inputs.items():
            parts.append(f"## {key.replace('_', ' ').title()}\n{value}")

        return "\n\n".join(parts)

    def _parse_response(self, response: Any) -> tuple[str, List[Dict]]:
        """
        Parse LLM response to extract text and tool calls.

        Uses the provider's response processor for format-agnostic parsing.
        """
        processor = self.llm_client._get_response_processor()
        if not processor:
            return "", []

        try:
            text_content = processor.extract_text_content(response)
            tool_calls = processor.extract_tool_calls(response)
            return text_content, tool_calls
        except Exception as e:
            print(f"[Agent] Error parsing response: {e}")
            return "", []

    async def _execute_tools(
        self,
        tool_calls: List[Dict],
        iteration: int
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Execute tool calls.

        Args:
            tool_calls: List of tool call dicts
            iteration: Current iteration number

        Returns:
            List of tool results
        """
        # Emit activity for each tool
        for tool_call in tool_calls:
            self._emit_activity("tool_call_start", {
                "tool": tool_call.get("name", "unknown"),
                "args": tool_call.get("arguments", {}),
            })

        # Create context adapter for ToolExecutor
        context = _ToolExecutionContext(agent_profile=self.definition.tool_profile)

        # Create ToolExecutor
        tool_executor = ToolExecutor(
            tool_manager=self.llm_client.tool_manager,
            message_service=MessageService(),
            session_id=self._execution_id or "",
        )

        # Generate message ID for tool execution
        message_id = f"agent_{self._execution_id}_{iteration}"

        # Execute all tools
        execution_result = await tool_executor.execute_all(
            tool_calls=tool_calls,
            message_id=message_id,
            context_manager=context,
        )

        # Emit completion activity for each tool
        for i, tool_call in enumerate(tool_calls):
            result = execution_result.results[i]
            status = result.get("status", "unknown") if result else "rejected"
            self._emit_activity("tool_call_end", {
                "tool": tool_call.get("name", "unknown"),
                "status": status,
            })

        return execution_result.results

    def _extract_summary(self, response_text: str) -> str:
        """Extract a brief summary from response text."""
        if not response_text:
            return "Task completed"

        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        if not lines:
            return "Task completed"

        first_line = lines[0]

        if first_line.startswith('#'):
            first_line = first_line.lstrip('#').strip()

        if len(first_line) > 100:
            return first_line[:97] + "..."

        return first_line

    def _emit_activity(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit activity event if callback is registered."""
        if not self.on_activity:
            return

        valid_types = [
            "started", "thinking", "tool_call_start", "tool_call_end",
            "llm_response", "completed", "error"
        ]
        if event_type not in valid_types:
            return

        activity = AgentActivity(
            agent_name=self.definition.name,
            event_type=event_type,  # type: ignore
            data=data,
        )
        self.on_activity(activity)
