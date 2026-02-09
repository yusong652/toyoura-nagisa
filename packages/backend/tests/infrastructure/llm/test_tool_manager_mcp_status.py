from typing import Any

import pytest

from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class _DummyToolManager(BaseToolManager):
    async def get_function_call_schemas(self, session_id: str, agent_profile="pfc_expert") -> Any:
        return []


class _DummyMcpManager:
    def __init__(self, result: dict[str, Any]):
        self._result = result

    async def call_tool(self, _tool_name: str, _tool_args: dict[str, Any]) -> dict[str, Any]:
        return self._result


@pytest.mark.asyncio
async def test_check_task_status_failed_task_is_not_tool_error(monkeypatch):
    manager = _DummyToolManager()
    mcp_result = {
        "status": "success",
        "server": "pfc",
        "content": [
            {
                "type": "text",
                "text": "Task status\n- task_id: 161c50\n- status: failed\n- error: detailed stacktrace",
            }
        ],
        "structuredContent": {
            "operation": "pfc_check_task_status",
            "status": "failed",
            "task_id": "161c50",
            "display": "Task status\n- task_id: 161c50\n- status: failed\n- error: detailed stacktrace",
            "error": "detailed stacktrace",
        },
    }

    import backend.infrastructure.mcp.client as mcp_client_module

    monkeypatch.setattr(mcp_client_module, "get_mcp_client_manager", lambda: _DummyMcpManager(mcp_result))

    result = await manager._execute_mcp_tool("pfc_check_task_status", {"task_id": "161c50"})

    assert result["status"] == "success"
    assert "failed" in result["llm_content"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_structured_failure_status_does_not_flip_tool_result_to_error(monkeypatch):
    manager = _DummyToolManager()
    mcp_result = {
        "status": "success",
        "server": "pfc",
        "content": [{"type": "text", "text": "pfc_execute_task failed\n- status: submission_failed"}],
        "structuredContent": {
            "operation": "pfc_execute_task",
            "status": "submission_failed",
            "message": "Failed to submit task",
            "display": "pfc_execute_task failed\n- status: submission_failed",
        },
    }

    import backend.infrastructure.mcp.client as mcp_client_module

    monkeypatch.setattr(mcp_client_module, "get_mcp_client_manager", lambda: _DummyMcpManager(mcp_result))

    result = await manager._execute_mcp_tool("pfc_execute_task", {"entry_script": "x.py", "description": "x"})

    assert result["status"] == "success"
    assert "submission_failed" in result["llm_content"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_call_error_status_is_reported_as_tool_error(monkeypatch):
    manager = _DummyToolManager()
    mcp_result = {
        "status": "error",
        "server": "pfc",
        "message": "Tool execution failed: bridge disconnected",
        "content": [{"type": "text", "text": "bridge disconnected"}],
        "structuredContent": None,
    }

    import backend.infrastructure.mcp.client as mcp_client_module

    monkeypatch.setattr(mcp_client_module, "get_mcp_client_manager", lambda: _DummyMcpManager(mcp_result))

    result = await manager._execute_mcp_tool("pfc_check_task_status", {"task_id": "161c50"})

    assert result["status"] == "error"
    assert "bridge disconnected" in result["message"]


@pytest.mark.asyncio
async def test_top_level_display_is_used_even_when_result_field_is_dict(monkeypatch):
    manager = _DummyToolManager()
    mcp_result = {
        "status": "success",
        "server": "pfc",
        "content": [{"type": "text", "text": '{"operation":"pfc_check_task_status","status":"completed"}'}],
        "structuredContent": {
            "operation": "pfc_check_task_status",
            "status": "completed",
            "result": {"output_path": "D:/x/test_plot.png"},
            "display": "Task status\n- task_id: 3786d3\n- status: completed",
        },
    }

    import backend.infrastructure.mcp.client as mcp_client_module

    monkeypatch.setattr(mcp_client_module, "get_mcp_client_manager", lambda: _DummyMcpManager(mcp_result))

    result = await manager._execute_mcp_tool("pfc_check_task_status", {"task_id": "3786d3"})

    assert result["status"] == "success"
    assert result["llm_content"]["parts"][0]["text"].startswith("Task status")
    assert '"operation"' not in result["llm_content"]["parts"][0]["text"]
