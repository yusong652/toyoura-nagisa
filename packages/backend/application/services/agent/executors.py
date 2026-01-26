"""
Agent Executors.

Provides separate execution loops for MainAgent and SubAgent to keep
the orchestration logic flat and focused.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from backend.application.services.message_service import MessageService
from backend.application.services.streaming_models import StreamingState
from backend.application.services.streaming_processor import StreamingProcessor
from backend.application.tools.runtime import ToolExecutor
from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

if TYPE_CHECKING:
    from backend.application.services.agent.core import Agent


class BaseAgentExecutor:
    """Base executor for shared Agent execution interface."""

    def __init__(self, agent: "Agent") -> None:
        self.agent = agent

    async def execute_loop(self) -> Any:
        raise NotImplementedError


class MainAgentExecutor(BaseAgentExecutor):
    """Executor for MainAgent streaming workflow."""

    async def execute_loop(self) -> Any:
        from backend.shared.exceptions import UserRejectionInterruption

        agent = self.agent
        agent._set_streaming_processor(StreamingProcessor(agent.llm_client, agent.session_id))

        iteration = 0
        while True:
            agent.status_monitor.set_iteration_context(iteration, agent.config.max_iterations)

            tool_schemas = await agent.llm_client.tool_manager.get_function_call_schemas(
                agent.session_id, agent.config.tool_profile
            )
            api_config = agent.llm_client._build_api_config(agent._system_prompt, tool_schemas)

            message_service = MessageService()
            agent._set_message_id(message_service.save_assistant_message([], agent.session_id))
            await WebSocketNotificationService.send_message_create(
                agent.session_id, agent._get_message_id(), streaming=True
            )
            agent.context_manager.streaming_message_id = agent._get_message_id()
            agent._set_stream_state(StreamingState(message_id=agent._get_message_id()))

            working_contents = agent.context_manager.get_working_contents()
            stream = agent.llm_client.call_api_with_context_streaming(working_contents, api_config)
            was_interrupted, response = await agent._get_streaming_processor().process_stream(
                stream, agent._get_stream_state()
            )

            if was_interrupted:
                return await agent._handle_stream_interruption(iteration)

            has_tools = agent._get_streaming_processor().has_tool_calls(response)
            tool_calls = agent._get_streaming_processor().extract_tool_calls(response) if has_tools else []

            if not has_tools:
                return await agent._finalize_stream_response(response)

            agent.context_manager.add_response(response)
            await agent._update_stream_tool_message(response, tool_calls)

            if iteration >= agent.config.max_iterations:
                await agent._handle_iteration_limit(tool_calls)
                return response

            tool_executor = ToolExecutor(
                agent.llm_client.tool_manager,
                agent.session_id,
                notification_session_id=agent._notification_session_id,
            )
            execution_result = await tool_executor.execute_all(
                tool_calls, agent._get_message_id(), agent.config.tool_profile
            )

            await tool_executor.save_results_to_context(tool_calls, execution_result.results, agent.context_manager)
            await tool_executor.save_results_to_database(tool_calls, execution_result.results)

            if execution_result.rejected_tools:
                if execution_result.rejection_outcome == "reject":
                    await agent._save_rejection_context(
                        execution_result.rejected_tools, execution_result.rejection_message
                    )
                    await WebSocketNotificationService.send_streaming_update(
                        session_id=agent.session_id,
                        message_id=agent._get_message_id(),
                        content=agent._get_stream_state().get_content_blocks(),
                        streaming=False,
                        interrupted=False,
                    )
                    raise UserRejectionInterruption(agent.session_id, execution_result.rejected_tools)
                if execution_result.rejection_outcome == "reject_and_tell":
                    print(f"[Agent] Tool rejected with instruction, continuing: {execution_result.rejection_message}")

            if agent.status_monitor.is_user_interrupted():
                print(f"[Agent] Tool calling interrupted by user at iteration {iteration}")
                await WebSocketNotificationService.send_streaming_update(
                    session_id=agent.session_id,
                    message_id=agent._get_stream_state().message_id,
                    content=agent._get_stream_state().get_content_blocks(),
                    streaming=False,
                    interrupted=True,
                )
                return response

            agent.status_monitor.todo_monitor.track_iteration()
            iteration += 1


class SubAgentExecutor(BaseAgentExecutor):
    """Executor for SubAgent non-streaming workflow."""

    async def execute_loop(self) -> Any:
        agent = self.agent

        iteration = 0
        while True:
            agent.status_monitor.set_iteration_context(iteration, agent.config.max_iterations)

            tool_schemas = await agent.llm_client.tool_manager.get_function_call_schemas(
                agent.session_id, agent.config.tool_profile
            )
            api_config = agent.llm_client._build_api_config(agent._system_prompt, tool_schemas)

            working_contents = agent.context_manager.get_working_contents()
            response = await agent.llm_client.call_api_with_context(
                context_contents=working_contents,
                api_config=api_config,
            )

            processor = agent.llm_client._get_response_processor()
            tool_calls = processor.extract_tool_calls(response)
            has_tools = bool(tool_calls)

            if not has_tools:
                agent.context_manager.add_response(response)
                return response

            agent.context_manager.add_response(response)

            if iteration >= agent.config.max_iterations:
                limit_result = await agent._handle_iteration_limit(tool_calls)
                return limit_result

            if agent._parent_tool_call_id:
                for tool_call in tool_calls:
                    await WebSocketNotificationService.send_subagent_tool_use(
                        session_id=agent._notification_session_id,
                        parent_tool_call_id=agent._parent_tool_call_id,
                        tool_call_id=tool_call.get("id", ""),
                        tool_name=tool_call.get("name", "unknown"),
                        tool_input=tool_call.get("arguments", {}),
                    )

            tool_executor = ToolExecutor(
                tool_manager=agent.llm_client.tool_manager,
                session_id=agent.session_id,
                notification_session_id=agent._notification_session_id,
                send_tool_result_notifications=False,
            )
            execution_result = await tool_executor.execute_all(
                tool_calls=tool_calls,
                message_id=f"agent_{agent.session_id}_{iteration}",
                agent_profile=agent.config.tool_profile,
            )

            if agent._parent_tool_call_id:
                for tool_call, result in zip(tool_calls, execution_result.results, strict=False):
                    is_error = result.get("status") == "error" if result else True
                    await WebSocketNotificationService.send_subagent_tool_result(
                        session_id=agent._notification_session_id,
                        parent_tool_call_id=agent._parent_tool_call_id,
                        tool_call_id=tool_call.get("id", ""),
                        tool_name=tool_call.get("name", "unknown"),
                        is_error=is_error,
                    )

            if execution_result.rejected_tools:
                if execution_result.rejection_outcome == "reject":
                    await agent._save_rejection_context(
                        execution_result.rejected_tools,
                        execution_result.rejection_message,
                        is_subagent=True,
                    )
                    return {"_subagent_rejected": True}

            await tool_executor.save_results_to_context(
                tool_calls, execution_result.results, agent.context_manager, inject_reminders=True
            )

            from backend.infrastructure.monitoring import get_status_monitor

            parent_monitor = get_status_monitor(agent._notification_session_id)
            if parent_monitor.is_user_interrupted():
                print(f"[SubAgent] Interrupted by user at iteration {iteration}")
                return {"_subagent_rejected": True}

            agent.status_monitor.todo_monitor.track_iteration()
            iteration += 1
