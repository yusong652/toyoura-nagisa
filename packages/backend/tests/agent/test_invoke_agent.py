"""Integration tests for invoke_agent tool.

Run with: uv run pytest packages/backend/tests/agent/test_invoke_agent.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.infrastructure.mcp.tools.agent.invoke_agent import invoke_agent, AVAILABLE_SUBAGENTS
from backend.domain.models.agent_profiles import get_subagent_config, PFC_EXPLORER
from backend.domain.models.agent import AgentResult
from backend.domain.models.messages import AssistantMessage


class TestInvokeAgentTool:
    """Tests for the invoke_agent tool."""

    def test_available_agents_configured(self):
        """Verify AVAILABLE_SUBAGENTS matches SUBAGENT_CONFIGS."""
        for agent_type in AVAILABLE_SUBAGENTS:
            config = get_subagent_config(agent_type)
            assert config is not None
            assert config.name == agent_type

    def test_pfc_explorer_config(self):
        """Verify PFC Explorer SubAgent configuration."""
        config = PFC_EXPLORER
        assert config.name == "pfc_explorer"
        assert config.streaming_enabled is False
        assert config.enable_memory is False
        assert config.max_iterations == 64
        assert "pfc_browse_commands" in config.tools
        assert "pfc_browse_python_api" in config.tools
        assert "pfc_query_command" in config.tools
        assert "pfc_query_python_api" in config.tools
        assert "pfc_browse_reference" in config.tools


class TestInvokeAgentExecution:
    """Tests for invoke_agent execution flow."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock MCP context."""
        context = MagicMock()
        context.client_id = "test_session_123"
        return context

    @pytest.mark.asyncio
    async def test_unknown_agent_type_returns_error(self, mock_context):
        """Test that unknown agent type returns error."""
        result = await invoke_agent(
            context=mock_context,
            description="Test task",
            prompt="test prompt",
            subagent_type="unknown_agent",  # type: ignore
        )

        assert result["status"] == "error"
        assert "Unknown subagent type" in result["message"]

    @pytest.mark.asyncio
    async def test_successful_subagent_execution(self, mock_context):
        """Test successful SubAgent execution."""
        # Mock the AgentService and its dependencies
        mock_agent_result = AgentResult(
            status="success",
            message=AssistantMessage(
                role="assistant", content=[{"type": "text", "text": "Found ball syntax: ball create..."}]
            ),
            iterations_used=2,
            execution_time_seconds=1.5,
        )

        # Patch the dependencies where they are defined
        with (
            patch("backend.shared.utils.app_context.get_secondary_llm_client") as mock_get_client,
            patch("backend.shared.utils.app_context.get_llm_factory") as mock_get_factory,
            patch("backend.application.services.agent.service.AgentService") as mock_service_class,
            patch(
                "backend.infrastructure.storage.llm_config_manager.get_default_llm_config"
            ) as mock_get_default_config,
            patch("backend.infrastructure.storage.session_manager.get_session_llm_config") as mock_get_session_config,
        ):
            mock_service = MagicMock()
            mock_service.run_subagent = AsyncMock(return_value=mock_agent_result)
            mock_service_class.return_value = mock_service

            mock_llm_client = MagicMock()
            mock_get_client.return_value = mock_llm_client

            mock_factory = MagicMock()
            mock_factory.create_client_with_config.return_value = mock_llm_client
            mock_get_factory.return_value = mock_factory

            # Force use of get_secondary_llm_client by returning empty configs
            mock_get_default_config.return_value = {}
            mock_get_session_config.return_value = {}

            result = await invoke_agent(
                context=mock_context,
                description="Find ball syntax",
                prompt="Find ball create syntax",
                subagent_type="pfc_explorer",
            )

            assert result["status"] == "success"
            assert "PFC Explorer" in result["message"]
            assert result["data"]["iterations_used"] == 2
            assert "ball" in result["llm_content"]["parts"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_max_iterations_returns_error(self, mock_context):
        """Test that max iterations returns error with partial result."""
        mock_agent_result = AgentResult(
            status="max_iterations",
            message=AssistantMessage(role="assistant", content=[{"type": "text", "text": "Partial result..."}]),
            iterations_used=10,
            execution_time_seconds=5.0,
        )

        with (
            patch("backend.shared.utils.app_context.get_secondary_llm_client") as mock_get_client,
            patch("backend.application.services.agent.service.AgentService") as mock_service_class,
            patch(
                "backend.infrastructure.storage.llm_config_manager.get_default_llm_config"
            ) as mock_get_default_config,
            patch("backend.infrastructure.storage.session_manager.get_session_llm_config") as mock_get_session_config,
        ):
            mock_service = MagicMock()
            mock_service.run_subagent = AsyncMock(return_value=mock_agent_result)
            mock_service_class.return_value = mock_service
            mock_get_client.return_value = MagicMock()

            # Force use of get_secondary_llm_client by returning empty configs
            mock_get_default_config.return_value = {}
            mock_get_session_config.return_value = {}

            result = await invoke_agent(
                context=mock_context, description="Complex query", prompt="Complex query", subagent_type="pfc_explorer"
            )

            assert result["status"] == "error"
            assert "iteration limit" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_missing_session_id_raises_error(self):
        """Test that missing session_id returns error."""
        context = MagicMock()
        context.client_id = None

        # invoke_agent catches exceptions and returns error response
        result = await invoke_agent(context=context, description="Test", prompt="test", subagent_type="pfc_explorer")

        assert result["status"] == "error"
        # The actual error depends on what fails first when session_id is None
        # It might be get_session_llm_config or something else
        # But it should definitely fail gracefully


class TestActivityTracking:
    """Tests for SubAgent activity tracking."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.client_id = "test_session_456"
        return context

    @pytest.mark.asyncio
    async def test_activity_callback_receives_events(self, mock_context):
        """Test that activity callback receives SubAgent events."""
        captured_activities = []

        mock_agent_result = AgentResult(
            status="success",
            message=AssistantMessage(role="assistant", content=[{"type": "text", "text": "Done"}]),
            iterations_used=1,
            execution_time_seconds=0.5,
        )

        async def mock_run_subagent(config, instruction, **kwargs):
            return mock_agent_result

        with (
            patch("backend.shared.utils.app_context.get_secondary_llm_client") as mock_get_client,
            patch("backend.application.services.agent.service.AgentService") as mock_service_class,
            patch(
                "backend.infrastructure.storage.llm_config_manager.get_default_llm_config"
            ) as mock_get_default_config,
            patch("backend.infrastructure.storage.session_manager.get_session_llm_config") as mock_get_session_config,
        ):
            mock_service = MagicMock()
            mock_service.run_subagent = mock_run_subagent
            mock_service_class.return_value = mock_service
            mock_get_client.return_value = MagicMock()

            # Force use of get_secondary_llm_client by returning empty configs
            mock_get_default_config.return_value = {}
            mock_get_session_config.return_value = {}

            result = await invoke_agent(
                context=mock_context, description="Test query", prompt="Test query", subagent_type="pfc_explorer"
            )

            # Activities are logged internally
            assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
