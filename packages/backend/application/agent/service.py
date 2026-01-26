"""
AgentService - Application layer service for Agent lifecycle management.

This service provides a clean interface for the presentation layer to interact
with Agent instances, encapsulating agent creation and execution logic.

Responsibilities:
- Agent instantiation with proper dependencies
- MainAgent chat processing (streaming with persistence)
- SubAgent task execution (non-streaming, temporary context)
- Dynamic LLM client creation based on global default configuration
- Separation of concerns: presentation layer doesn't know Agent internals
"""

from typing import Any

from backend.application.agent.core import Agent
from backend.domain.models.agent import AgentResult
from backend.domain.models.agent_profiles import AgentConfig, get_agent_config
from backend.domain.models.messages import UserMessage
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.factory import LLMFactory


class AgentService:
    """
    Application layer service for managing Agent lifecycle.

    This service bridges the presentation layer and the Agent class,
    providing a simplified interface for chat processing and task execution.

    Usage:
        # In presentation layer (e.g., chat_request_handler)
        service = AgentService(llm_client, llm_factory)

        # With default configuration (from config files)
        result = await service.process_chat(
            session_id=session_id,
            instruction=user_message,
        )

        # With custom configuration (from global default_llm.json)
        result = await service.process_chat(
            session_id=session_id,
            instruction=user_message,
            llm_config={"provider": "anthropic", "model": "claude-sonnet-4-5"}
        )

        # For SubAgent execution
        from backend.domain.models.agent_profiles import PFC_EXPLORER
        result = await service.run_subagent(
            config=PFC_EXPLORER,
            instruction="Find ball syntax",
        )
    """

    def __init__(self, llm_client: LLMClientBase, llm_factory: LLMFactory | None = None):
        """
        Initialize AgentService.

        Args:
            llm_client: Default LLM client instance (typically from app.state)
            llm_factory: LLM factory for creating custom clients based on config.
                        If None, custom LLM configs will not be supported.
        """
        self._llm_client = llm_client
        self._llm_factory = llm_factory

    async def process_chat(
        self,
        session_id: str,
        instruction: UserMessage,
        enable_memory: bool = True,
        llm_config: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Process a chat request using MainAgent.

        Creates a MainAgent with the standard configuration and executes
        the conversation turn with full streaming support.

        If llm_config is provided, creates a custom LLM client using the specified
        provider and model. Otherwise, uses the default LLM client.

        Args:
            session_id: Session ID for the conversation
            instruction: UserMessage object containing user input
            enable_memory: Whether to enable memory persistence (default: True)
            llm_config: Optional LLM configuration with keys:
                       - provider: LLM provider name (e.g., "google", "anthropic")
                       - model: Model identifier (e.g., "gemini-2.0-flash-exp")
                       If provided, this overrides the default client.

        Returns:
            AgentResult with execution outcome and response message

        Raises:
            ValueError: If llm_config is provided but llm_factory is not available,
                       or if the configuration is invalid
        """
        # Determine which LLM client to use
        llm_client = self._llm_client

        if llm_config:
            if not self._llm_factory:
                raise ValueError("Cannot use custom LLM config: LLMFactory not provided during initialization")

            # Validate config structure
            if "provider" not in llm_config or "model" not in llm_config:
                raise ValueError("Invalid LLM config: must contain 'provider' and 'model' keys")

            # Create custom client based on provided config
            llm_client = self._llm_factory.create_client_with_config(
                provider=llm_config["provider"], model=llm_config["model"]
            )

        config = get_agent_config()
        agent = Agent(
            config=config,
            llm_client=llm_client,
            session_id=session_id,
            enable_memory=enable_memory,
        )
        return await agent.execute(instruction=instruction)

    async def run_subagent(
        self,
        config: AgentConfig,
        instruction: str,
        context: str | None = None,
        notification_session_id: str | None = None,
        parent_tool_call_id: str | None = None,
    ) -> AgentResult:
        """
        Execute a SubAgent task.

        Creates a SubAgent (no persistent session) and executes
        the given instruction in non-streaming mode.

        Args:
            config: AgentConfig for the SubAgent
            instruction: Task instruction to execute (string)
            context: Optional additional context to prepend
            notification_session_id: Session ID for WebSocket notifications.
                                    If provided, confirmation requests will be routed
                                    to this session (typically MainAgent's session).
            parent_tool_call_id: ID of the parent tool call (invoke_agent) for
                                frontend to associate SubAgent tool uses.

        Returns:
            AgentResult with execution outcome
        """
        if config.is_main_agent:
            raise ValueError("SubAgent execution requires is_main_agent=False")

        # Build full instruction with context
        full_instruction = instruction
        if context:
            full_instruction = f"{context}\n\n{instruction}"

        # Convert string to UserMessage
        user_message = UserMessage(content=full_instruction)

        agent = Agent(
            config=config,
            llm_client=self._llm_client,
            notification_session_id=notification_session_id,
            parent_tool_call_id=parent_tool_call_id,
        )
        return await agent.execute(instruction=user_message)

    @property
    def llm_client(self) -> LLMClientBase:
        """Access the underlying LLM client (for context manager operations)."""
        return self._llm_client
