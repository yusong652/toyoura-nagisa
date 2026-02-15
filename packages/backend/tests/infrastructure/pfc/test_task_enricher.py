from types import SimpleNamespace
from typing import Any, cast

from backend.infrastructure.pfc.task_enricher import _enrich_check_status, enrich_pfc_result


class _FakeTaskManager:
    def __init__(self, git_commit: str | None):
        self._task = SimpleNamespace(git_commit=git_commit) if git_commit is not None else None

    def get_task(self, _task_id: str):
        return self._task


def _build_result():
    return {
        "llm_content": {
            "parts": [
                {
                    "type": "text",
                    "text": "Task status\n- task_id: fc131c\n- status: completed",
                }
            ]
        },
        "data": {
            "structuredContent": {
                "ok": True,
                "data": {
                    "task_id": "fc131c",
                    "task_status": "completed",
                },
            }
        },
    }


def test_enrich_check_status_injects_git_commit_into_structured_content():
    result = _build_result()

    _enrich_check_status(result, cast(Any, _FakeTaskManager("3a9587a9f3d2")))

    payload = result["data"]["structuredContent"]["data"]
    assert payload["git_commit"] == "3a9587a"


def test_enrich_check_status_skips_when_local_task_has_no_git_commit():
    result = _build_result()

    _enrich_check_status(result, cast(Any, _FakeTaskManager(None)))

    payload = result["data"]["structuredContent"]["data"]
    assert "git_commit" not in payload


def test_enrich_check_status_injects_git_commit_into_llm_content_text():
    result = _build_result()

    _enrich_check_status(result, cast(Any, _FakeTaskManager("3a9587a9f3d2")))

    text = result["llm_content"]["parts"][0]["text"]
    assert "- git_commit: 3a9587a" in text


def test_enrich_check_status_supports_legacy_structured_content_shape(monkeypatch):
    result = {
        "llm_content": {
            "parts": [
                {
                    "type": "text",
                    "text": "Task status\n- task_id: fc131c\n- status: completed",
                }
            ]
        },
        "data": {
            "structuredContent": {
                "operation": "pfc_check_task_status",
                "status": "completed",
                "task_id": "fc131c",
            }
        },
    }

    class _Tm:
        tasks = {"fc131c": True}

        def get_task(self, _task_id: str):
            return SimpleNamespace(git_commit="abcdef123456")

    monkeypatch.setattr("backend.infrastructure.pfc.task_manager.get_pfc_task_manager", lambda: _Tm())

    out = enrich_pfc_result("pfc_check_task_status", result)

    assert out["data"]["structuredContent"]["git_commit"] == "abcdef1"
    assert "- git_commit: abcdef1" in out["llm_content"]["parts"][0]["text"]
