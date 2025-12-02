"""
AgentExecutor - Universal agent execution engine.

This module provides the core execution loop for SubAgents,
supporting non-streaming LLM calls with tool execution.
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.domain.models.agent import AgentActivity, AgentDefinition, AgentResult
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.services.conversation.tool_executor import ToolExecutor
from backend.application.services.message_service import MessageService


class SubAgentContext:
    """
    Minimal context adapter for SubAgent tool execution.

    Provides the interface expected by ToolExecutor.
    """

    def __init__(self, agent_profile: str):
        self.agent_profile = agent_profile

    async def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Dict[str, Any],
        inject_reminders: bool = False
    ) -> None:
        """No-op for SubAgent - results handled internally."""
        pass


class AgentExecutor:
    """
    Universal agent executor for SubAgents.

    Handles the complete execution lifecycle:
    1. Build initial context from definition and inputs
    2. Execute LLM call (non-streaming)
    3. Process tool calls if any
    4. Repeat until done or limits reached

    Unlike ChatOrchestrator, this executor:
    - Uses non-streaming LLM calls
    - Does not require user confirmation for tools
    - Does not persist messages to database
    - Does not send WebSocket notifications
    - Emits activity events via callback instead
    """

    def __init__(
        self,
        definition: AgentDefinition,
        llm_client: LLMClientBase,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ):
        """
        Initialize AgentExecutor.

        Args:
            definition: Agent configuration
            llm_client: LLM client for API calls
            on_activity: Optional callback for activity events
        """
        self.definition = definition
        self.llm_client = llm_client
        self.on_activity = on_activity

        # Generate unique execution ID for this run
        self.execution_id = str(uuid.uuid4())[:8]

    async def run(
        self,
        inputs: Dict[str, str],
        abort_signal: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """
        Execute agent with given inputs.

        Args:
            inputs: Template variables (e.g., {"objective": "...", "context": "..."})
            abort_signal: Optional event to signal abort

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.time()
        iteration = 0

        self._emit_activity("started", {"inputs": inputs})

        try:
            # Setup context manager for this execution
            context_manager = self.llm_client.get_or_create_context_manager(self.execution_id)
            context_manager.agent_profile = self.definition.tool_profile
            context_manager.enable_memory = self.definition.enable_memory

            # Build initial user message from inputs (task from parent agent)
            # Reuse the same mechanism as main agent: context_manager.add_user_message()
            from backend.domain.models.messages import UserMessage
            initial_message = UserMessage(content=self._build_prompt_content(inputs))
            await context_manager.add_user_message(initial_message)

            # Get api_config using _prepare_complete_context (reuses provider logic)
            # Now working_contents contains the initial user message
            messages, api_config = await self.llm_client._prepare_complete_context(
                session_id=self.execution_id,
                system_prompt=self.definition.system_prompt  # Fixed system prompt, no template
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

                # LLM call - get fresh messages from context_manager each iteration
                messages = context_manager.get_working_contents()

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

                # Add assistant response to context (reuse infrastructure)
                context_manager.add_response(response)

                # Generate message ID for tool execution
                tool_message_id = f"subagent_{self.execution_id}_{iteration}"

                # Execute tools and add results to context
                tool_results = await self._execute_tools(tool_calls, tool_message_id)
                for tool_call, result in zip(tool_calls, tool_results):
                    if result is not None:
                        await context_manager.add_tool_result(
                            tool_call_id=tool_call.get("id", ""),
                            tool_name=tool_call.get("name", ""),
                            result=result,
                            inject_reminders=False  # SubAgent doesn't need reminders
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

    def _build_prompt_content(self, inputs: Dict[str, str]) -> str:
        """
        Build prompt content from inputs for initial user message.

        The format is flexible - this is the task message from parent agent.
        For SubAgent, typically includes objective and context.
        For Main Agent (future), this would be the actual user input.

        Args:
            inputs: Task inputs (e.g., {"objective": "...", "context": "..."})

        Returns:
            Prompt string for the initial user message
        """
        # Simple format: just concatenate inputs
        # Parent agent controls the exact format
        if len(inputs) == 1:
            # Single input - use directly
            return str(list(inputs.values())[0])

        # Multiple inputs - format as sections
        parts = []
        for key, value in inputs.items():
            parts.append(f"## {key.replace('_', ' ').title()}\n{value}")

        return "\n\n".join(parts)

    def _parse_response(self, response: Any) -> tuple[str, List[Dict]]:
        """
        Parse LLM response to extract text and tool calls.

        Uses the provider's response processor for format-agnostic parsing.

        Returns:
            Tuple of (response_text, tool_calls)
        """
        processor = self.llm_client._get_response_processor()
        if not processor:
            return "", []

        try:
            # Use response processor's standard methods
            text_content = processor.extract_text_content(response)
            tool_calls = processor.extract_tool_calls(response)
            return text_content, tool_calls
        except Exception as e:
            print(f"[AgentExecutor] Error parsing response: {e}")
            return "", []

    async def _execute_tools(
        self,
        tool_calls: List[Dict],
        message_id: str
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Execute tool calls using ToolExecutor (with confirmation support).

        Args:
            tool_calls: List of tool call dicts
            message_id: Message ID for tool execution context

        Returns:
            List of tool results (may contain None for rejected tools)
        """
        # Emit activity for each tool
        for tool_call in tool_calls:
            self._emit_activity("tool_call_start", {
                "tool": tool_call.get("name", "unknown"),
                "args": tool_call.get("arguments", {}),
            })

        # Create context adapter for ToolExecutor
        context = SubAgentContext(agent_profile=self.definition.tool_profile)

        # Create ToolExecutor
        tool_executor = ToolExecutor(
            tool_manager=self.llm_client.tool_manager,
            message_service=MessageService(),
            session_id=self.execution_id,
        )

        # Execute all tools (with confirmation if needed)
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
        """
        Extract a brief summary from response text.

        Takes first meaningful line or truncates.
        """
        if not response_text:
            return "Task completed"

        # Take first non-empty line
        lines = [l.strip() for l in response_text.split('\n') if l.strip()]
        if not lines:
            return "Task completed"

        first_line = lines[0]

        # Remove markdown headers
        if first_line.startswith('#'):
            first_line = first_line.lstrip('#').strip()

        # Truncate if too long
        if len(first_line) > 100:
            return first_line[:97] + "..."

        return first_line

    def _emit_activity(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit activity event if callback is registered.
        """
        if not self.on_activity:
            return

        # Filter out typing issues
        valid_types = ["started", "thinking", "tool_call_start", "tool_call_end",
                       "llm_response", "completed", "error"]
        if event_type not in valid_types:
            return

        activity = AgentActivity(
            agent_name=self.definition.name,
            event_type=event_type,  # type: ignore
            data=data,
        )
        self.on_activity(activity)
