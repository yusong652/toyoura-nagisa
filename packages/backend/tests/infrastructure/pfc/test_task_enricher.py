from types import SimpleNamespace
from typing import Any, cast

from backend.infrastructure.pfc.task_enricher import _enrich_check_status


class _FakeTaskManager:
    def __init__(self, git_commit: str | None):
        self._task = SimpleNamespace(git_commit=git_commit) if git_commit is not None else None

    def get_task(self, _task_id: str):
        return self._task


def _build_result(display_text: str = "Task status\n- checked: n/a", llm_text: str | None = None):
    if llm_text is None:
        llm_text = display_text

    return {
        "data": {
            "structuredContent": {
                "task_id": "fc131c",
                "status": "completed",
                "display": display_text,
            }
        },
        "llm_content": {"parts": [{"type": "text", "text": llm_text}]},
    }


def test_enrich_check_status_injects_git_commit_into_display_and_mirrors_to_llm():
    result = _build_result(llm_text="stale llm text")

    _enrich_check_status(result, cast(Any, _FakeTaskManager("3a9587a9f3d2")))

    structured = result["data"]["structuredContent"]
    expected_display = "Task status\n- checked: n/a\n- git_commit: 3a9587a"

    assert structured["git_commit"] == "3a9587a"
    assert structured["display"] == expected_display
    assert result["llm_content"]["parts"][0]["text"] == expected_display
    assert "pfc_tracking" not in result["data"]


def test_enrich_check_status_skips_when_local_task_has_no_git_commit():
    result = _build_result("Task status\n- checked: true")

    _enrich_check_status(result, cast(Any, _FakeTaskManager(None)))

    structured = result["data"]["structuredContent"]
    assert "git_commit" not in structured
    assert "pfc_tracking" not in result["data"]


def test_enrich_check_status_creates_llm_content_from_display_when_missing():
    result = {
        "data": {
            "structuredContent": {
                "task_id": "fc131c",
                "status": "completed",
                "display": "Task status\n- checked: n/a",
            }
        }
    }

    _enrich_check_status(result, cast(Any, _FakeTaskManager("3a9587a9f3d2")))

    assert result["llm_content"]["parts"][0]["text"] == "Task status\n- checked: n/a\n- git_commit: 3a9587a"
