from types import SimpleNamespace
from typing import Any, cast

from backend.infrastructure.pfc.task_enricher import _enrich_check_status


class _FakeTaskManager:
    def __init__(self, git_commit: str | None):
        self._task = SimpleNamespace(git_commit=git_commit) if git_commit is not None else None

    def get_task(self, _task_id: str):
        return self._task


def _build_result():
    return {
        "data": {
            "structuredContent": {
                "task_id": "fc131c",
                "status": "completed",
            }
        },
    }


def test_enrich_check_status_injects_git_commit_into_structured_content():
    result = _build_result()

    _enrich_check_status(result, cast(Any, _FakeTaskManager("3a9587a9f3d2")))

    structured = result["data"]["structuredContent"]
    assert structured["git_commit"] == "3a9587a"


def test_enrich_check_status_skips_when_local_task_has_no_git_commit():
    result = _build_result()

    _enrich_check_status(result, cast(Any, _FakeTaskManager(None)))

    structured = result["data"]["structuredContent"]
    assert "git_commit" not in structured
