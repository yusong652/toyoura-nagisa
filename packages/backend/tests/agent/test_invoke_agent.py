"""Unit tests for invoke_agent tool configuration.

Run with: uv run pytest packages/backend/tests/agent/test_invoke_agent.py -v

Note: Integration tests that require full mocking of AgentService are skipped
due to the complexity of mocking internal function imports.
"""

import pytest
from unittest.mock import MagicMock

from backend.application.tools.agent.invoke_agent import invoke_agent, AVAILABLE_SUBAGENTS
from backend.domain.models.agent_profiles import get_subagent_config, PFC_EXPLORER


class TestInvokeAgentTool:
    """Tests for the invoke_agent tool configuration."""

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
        assert config.max_iterations == 128
        assert "pfc_browse_commands" in config.tools
        assert "pfc_browse_python_api" in config.tools
        assert "pfc_query_command" in config.tools
        assert "pfc_query_python_api" in config.tools
        assert "pfc_browse_reference" in config.tools


class TestInvokeAgentValidation:
    """Tests for invoke_agent input validation."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        context = MagicMock()
        context.session_id = "test_session_123"
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
        assert "available_subagents" in result.get("data", {})

    @pytest.mark.asyncio
    async def test_missing_session_id_returns_error(self):
        """Test that missing session_id returns error."""
        context = MagicMock()
        context.session_id = None

        result = await invoke_agent(
            context=context,
            description="Test",
            prompt="test",
            subagent_type="pfc_explorer",
        )

        assert result["status"] == "error"
        assert "session" in result["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
