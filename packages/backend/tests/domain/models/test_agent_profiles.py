import pytest

from backend.domain.models.agent_profiles import (
    AgentProfile,
    PROFILE_CONFIGS,
    PFC_TOOLS,
    SUBAGENT_PFC_EXPLORER_TOOLS,
    SUBAGENT_PFC_DIAGNOSTIC_TOOLS,
    get_profile_config,
    get_tools_for_profile,
    get_all_profiles,
    get_subagent_config,
    get_skills_for_profile,
)


def test_get_profile_config_by_name_and_enum():
    config_by_enum = get_profile_config(AgentProfile.PFC_EXPERT)
    config_by_name = get_profile_config("pfc_expert")

    assert config_by_enum is config_by_name
    assert config_by_enum.display_name == "PFC Expert"


def test_get_profile_config_invalid_name_raises():
    with pytest.raises(ValueError):
        get_profile_config("unknown")


def test_profile_config_properties():
    config = PROFILE_CONFIGS[AgentProfile.PFC_EXPERT]

    assert config.tool_profile == "pfc_expert"
    assert config.tool_count == len(PFC_TOOLS)
    assert config.estimated_tokens == len(PFC_TOOLS) * 282


def test_get_tools_for_profile_handles_subagent():
    tools = get_tools_for_profile("pfc_explorer")

    assert tools == SUBAGENT_PFC_EXPLORER_TOOLS
    assert "invoke_agent" not in tools


def test_get_all_profiles_includes_display_metadata():
    profiles = get_all_profiles()
    expert = profiles["pfc_expert"]

    assert expert["tool_count"] == len(PFC_TOOLS)
    assert expert["estimated_tokens"] == len(PFC_TOOLS) * 282
    assert expert["color"] == PROFILE_CONFIGS[AgentProfile.PFC_EXPERT].color
    assert expert["icon"] == PROFILE_CONFIGS[AgentProfile.PFC_EXPERT].icon


def test_get_subagent_config_returns_expected_tools():
    diagnostic = get_subagent_config("pfc_diagnostic")

    assert list(diagnostic.tools) == SUBAGENT_PFC_DIAGNOSTIC_TOOLS
    assert "invoke_agent" not in diagnostic.tools


def test_get_skills_for_profile_handles_subagents():
    assert get_skills_for_profile("pfc_explorer") == []
    assert get_skills_for_profile("pfc_diagnostic") == []


def test_get_skills_for_profile_returns_profile_skills():
    skills = get_skills_for_profile("pfc_expert")
    assert skills == list(PROFILE_CONFIGS[AgentProfile.PFC_EXPERT].skills)
