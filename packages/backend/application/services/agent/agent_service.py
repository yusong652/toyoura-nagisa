"""
AgentService - Application layer service for Agent lifecycle management.

This service provides a clean interface for the presentation layer to interact
with Agent instances, encapsulating agent creation and execution logic.

Responsibilities:
- Agent instantiation with proper dependencies
- MainAgent chat processing (streaming with persistence)
- SubAgent task execution (non-streaming, temporary context)
- Separation of concerns: presentation layer doesn't know Agent internals
"""

from typing import Callable, Optional

from backend.application.services.agent.agent import Agent
from backend.domain.models.agent import AgentActivity, AgentDefinition, AgentResult
from backend.domain.models.agent_definitions import MAIN_AGENT
from backend.infrastructure.llm.base.client import LLMClientBase


class AgentService:
    """
    Application layer service for managing Agent lifecycle.

    This service bridges the presentation layer and the Agent class,
    providing a simplified interface for chat processing and task execution.

    Usage:
        # In presentation layer (e.g., chat_request_handler)
        service = AgentService(llm_client)
        result = await service.process_chat(session_id)

        # For SubAgent execution
        result = await service.run_subagent(
            definition=PFC_EXPLORER,
            instruction="Find ball syntax",
            on_activity=progress_callback
        )
    """

    def __init__(self, llm_client: LLMClientBase):
        """
        Initialize AgentService.

        Args:
            llm_client: LLM client instance (typically from app.state)
        """
        self._llm_client = llm_client

    async def process_chat(self, session_id: str) -> AgentResult:
        """
        Process a chat request using MainAgent.

        Creates a MainAgent bound to the given session and executes
        the conversation turn with full streaming support.

        Args:
            session_id: Session ID for the conversation

        Returns:
            AgentResult with execution outcome and response message
        """
        agent = Agent(
            definition=MAIN_AGENT,
            llm_client=self._llm_client,
            session_id=session_id,
        )
        return await agent.execute()

    async def run_subagent(
        self,
        definition: AgentDefinition,
        instruction: str,
        context: Optional[str] = None,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ) -> AgentResult:
        """
        Execute a SubAgent task.

        Creates a SubAgent (no persistent session) and executes
        the given instruction in non-streaming mode.

        Args:
            definition: AgentDefinition for the SubAgent
            instruction: Task instruction to execute
            context: Optional additional context
            on_activity: Optional callback for activity events

        Returns:
            AgentResult with execution outcome
        """
        agent = Agent(
            definition=definition,
            llm_client=self._llm_client,
            on_activity=on_activity,
        )
        return await agent.execute(instruction=instruction, context=context)

    @property
    def llm_client(self) -> LLMClientBase:
        """Access the underlying LLM client (for context manager operations)."""
        return self._llm_client
