"""Tests for PfcTaskNotificationService parsing and normalization logic."""

import pytest

from backend.application.notifications.pfc_task_notification_service import (
    PfcTaskNotificationService,
)
from unittest.mock import AsyncMock


@pytest.fixture()
def service():
    mock_cm = AsyncMock()
    mock_cm.is_connected = AsyncMock(return_value=True)
    mock_cm.send_json = AsyncMock(return_value=True)
    return PfcTaskNotificationService(connection_manager=mock_cm)


# ── Status Normalization ─────────────────────────────────


class TestNormalizeStatus:
    def test_success_maps_to_completed(self, service):
        assert service._normalize_status("success") == "completed"
        assert service._normalize_status("completed") == "completed"

    def test_error_maps_to_failed(self, service):
        assert service._normalize_status("error") == "failed"
        assert service._normalize_status("failed") == "failed"

    def test_interrupted(self, service):
        assert service._normalize_status("interrupted") == "interrupted"

    def test_pending(self, service):
        assert service._normalize_status("pending") == "pending"

    def test_running_variants(self, service):
        assert service._normalize_status("running") == "running"
        assert service._normalize_status("submitted") == "running"

    def test_not_found(self, service):
        assert service._normalize_status("not_found") == "not_found"

    def test_unknown_defaults_to_running(self, service):
        assert service._normalize_status("something_else") == "running"
        assert service._normalize_status("") == "running"

    def test_fuzzy_match(self, service):
        assert service._normalize_status("task completed successfully") == "completed"
        assert service._normalize_status("error: timeout") == "failed"


# ── Structured Response Parsing ──────────────────────────


class TestParseStructuredResponse:
    def test_parses_direct_payload(self, service):
        result = {
            "structuredContent": {
                "ok": True,
                "data": {
                    "task_status": "completed",
                    "output": "Cycle 1000 done",
                    "error": None,
                    "result": "max_force=0.01",
                },
            }
        }
        parsed = service._parse_task_status_structured(result)
        assert parsed is not None
        assert parsed["status"] == "completed"
        assert parsed["output"] == "Cycle 1000 done"
        assert parsed["error"] is None

    def test_parses_running_payload(self, service):
        result = {
            "structuredContent": {
                "ok": True,
                "data": {
                    "task_status": "running",
                    "output": "line1\nline2",
                    "error": None,
                },
            }
        }
        parsed = service._parse_task_status_structured(result)
        assert parsed is not None
        assert parsed["status"] == "running"
        assert "line1" in parsed["output"]

    def test_parses_error_envelope(self, service):
        result = {
            "structuredContent": {
                "ok": False,
                "error": {"code": "not_found", "message": "Task not found"},
            }
        }
        parsed = service._parse_task_status_structured(result)
        assert parsed is not None
        assert parsed["status"] == "failed"
        assert parsed["error"] == "Task not found"

    def test_returns_none_without_structured_content(self, service):
        assert service._parse_task_status_structured({}) is None
        assert service._parse_task_status_structured({"structuredContent": "text"}) is None

    def test_filters_none_error(self, service):
        result = {
            "structuredContent": {
                "ok": True,
                "data": {
                    "task_status": "completed",
                    "output": "",
                    "error": "None",
                },
            }
        }
        parsed = service._parse_task_status_structured(result)
        assert parsed["error"] is None

    def test_filters_na_error(self, service):
        result = {
            "structuredContent": {
                "ok": True,
                "data": {
                    "task_status": "completed",
                    "output": "",
                    "error": "n/a",
                },
            }
        }
        parsed = service._parse_task_status_structured(result)
        assert parsed["error"] is None


# ── Text Response Parsing ────────────────────────────────


class TestParseTextResponse:
    def test_parses_running_task(self, service):
        text = (
            "Task status\n"
            "- task_id: abc123\n"
            "- status: running\n"
            "- start_time: 2026-02-11T10:00:00\n"
            "- error: None\n"
            "\n"
            "Output (2 lines, showing 1-2):\n"
            "Cycle 100: unbalanced=1e-3\n"
            "Cycle 200: unbalanced=5e-4\n"
        )
        parsed = service._parse_task_status_text(text)
        assert parsed is not None
        assert parsed["status"] == "running"
        assert parsed["error"] is None
        assert "Cycle 100" in parsed["output"]
        assert "Cycle 200" in parsed["output"]

    def test_parses_completed_task(self, service):
        text = (
            "Task status\n"
            "- status: completed\n"
            "- result: {'balls': 5000}\n"
            "- error: None\n"
            "\n"
            "Output (1 lines, showing 1-1):\n"
            "Done\n"
        )
        parsed = service._parse_task_status_text(text)
        assert parsed["status"] == "completed"
        assert parsed["result"] == "{'balls': 5000}"

    def test_parses_failed_task(self, service):
        text = (
            "Task status\n"
            "- status: failed\n"
            "- error: Script timeout after 30s\n"
        )
        parsed = service._parse_task_status_text(text)
        assert parsed["status"] == "failed"
        assert "timeout" in parsed["error"]

    def test_returns_none_for_empty(self, service):
        assert service._parse_task_status_text("") is None
        assert service._parse_task_status_text(None) is None

    def test_stops_at_next_hint(self, service):
        text = (
            "- status: running\n"
            "Output (5 lines):\n"
            "line1\n"
            "line2\n"
            "Next: skip_newest=2\n"
            "this should not appear\n"
        )
        parsed = service._parse_task_status_text(text)
        assert "this should not appear" not in parsed["output"]


# ── Recent Lines ─────────────────────────────────────────


class TestGetRecentLines:
    def test_returns_last_n_lines(self, service):
        output = "\n".join(f"line{i}" for i in range(20))
        lines = service._get_recent_lines(output)
        assert len(lines) == service.RECENT_OUTPUT_LINES
        assert lines[-1] == "line19"

    def test_empty_output(self, service):
        assert service._get_recent_lines("") == []
        assert service._get_recent_lines(None) == []
