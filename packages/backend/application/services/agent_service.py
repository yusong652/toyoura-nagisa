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

from backend.application.services.agent import Agent
from backend.domain.models.agent import AgentActivity, AgentResult
from backend.domain.models.agent_profiles import (
    SubAgentConfig,
    get_profile_config,
)
from backend.domain.models.messages import UserMessage
from backend.infrastructure.llm.base.client import LLMClientBase


class AgentService:
    """
    Application layer service for managing Agent lifecycle.

    This service bridges the presentation layer and the Agent class,
    providing a simplified interface for chat processing and task execution.

    Usage:
        # In presentation layer (e.g., chat_request_handler)
        service = AgentService(llm_client)
        result = await service.process_chat(
            session_id=session_id,
            instruction=user_message,
            agent_profile="coding"
        )

        # For SubAgent execution
        from backend.domain.models.agent_profiles import PFC_EXPLORER
        result = await service.run_subagent(
            config=PFC_EXPLORER,
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

    async def process_chat(
        self,
        session_id: str,
        instruction: UserMessage,
        agent_profile: str = "general",
        enable_memory: bool = True,
    ) -> AgentResult:
        """
        Process a chat request using MainAgent.

        Creates a MainAgent with the appropriate configuration based on profile
        and executes the conversation turn with full streaming support.

        Args:
            session_id: Session ID for the conversation
            instruction: UserMessage object containing user input
            agent_profile: Agent profile for tool selection (default: "general")
            enable_memory: Whether to enable memory persistence (default: True)

        Returns:
            AgentResult with execution outcome and response message
        """
        config = get_profile_config(agent_profile)
        agent = Agent(
            config=config,
            llm_client=self._llm_client,
            session_id=session_id,
            enable_memory=enable_memory,
        )
        return await agent.execute(instruction=instruction)

    async def run_subagent(
        self,
        config: SubAgentConfig,
        instruction: str,
        context: Optional[str] = None,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ) -> AgentResult:
        """
        Execute a SubAgent task.

        Creates a SubAgent (no persistent session) and executes
        the given instruction in non-streaming mode.

        Args:
            config: SubAgentConfig for the SubAgent
            instruction: Task instruction to execute (string)
            context: Optional additional context to prepend
            on_activity: Optional callback for activity events

        Returns:
            AgentResult with execution outcome
        """
        # Build full instruction with context
        full_instruction = instruction
        if context:
            full_instruction = f"{context}\n\n{instruction}"

        # Convert string to UserMessage
        user_message = UserMessage(content=full_instruction)

        agent = Agent(
            config=config,
            llm_client=self._llm_client,
            on_activity=on_activity,
        )
        return await agent.execute(instruction=user_message)

    @property
    def llm_client(self) -> LLMClientBase:
        """Access the underlying LLM client (for context manager operations)."""
        return self._llm_client
