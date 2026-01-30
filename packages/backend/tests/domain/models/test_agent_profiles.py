from backend.domain.models.agent_profiles import (
    MAIN_AGENT_CONFIG,
    get_agent_config,
    get_subagent_config,
    get_tools_for_agent,
    get_skills_for_agent,
)


def test_get_agent_config_returns_main_agent():
    config = get_agent_config()
    assert config is MAIN_AGENT_CONFIG
    assert config.display_name == "PFC Expert"
    assert config.is_main_agent is True


def test_agent_config_properties():
    config = get_agent_config()
    assert config.name == "pfc_expert"
    assert config.tool_count == len(config.tools)
    assert config.estimated_tokens == len(config.tools) * 282


def test_get_tools_for_agent_handles_subagent():
    tools = get_tools_for_agent("pfc_explorer")
    assert tools == list(get_subagent_config("pfc_explorer").tools)
    assert "invoke_agent" not in tools


def test_get_tools_for_agent_main():
    tools = get_tools_for_agent("pfc_expert")
    assert tools == list(get_agent_config().tools)


def test_get_subagent_config_returns_expected_tools():
    diagnostic = get_subagent_config("pfc_diagnostic")
    assert list(diagnostic.tools) == list(get_subagent_config("pfc_diagnostic").tools)
    assert "invoke_agent" not in diagnostic.tools
    assert diagnostic.is_main_agent is False


def test_get_skills_for_agent():
    assert get_skills_for_agent("pfc_explorer") == []
    assert get_skills_for_agent("pfc_diagnostic") == []
    assert get_skills_for_agent("pfc_expert") == list(MAIN_AGENT_CONFIG.skills)
