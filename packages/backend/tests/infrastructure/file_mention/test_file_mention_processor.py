import pytest
from typing import Optional, Dict, Any, cast
from unittest.mock import AsyncMock, Mock, call

from backend.infrastructure.file_mention.file_mention_processor import FileMentionProcessor, FileContent
from backend.application.tools.coding.utils.file_reader import (
    ProcessingResult,
    ContentFormat,
    FileType,
)
import backend.infrastructure.file_mention.file_mention_processor as processor_module
import backend.infrastructure.llm.session_client as session_client


def _make_processing_result(
    content,
    content_format=ContentFormat.TEXT,
    file_type=FileType.TEXT,
    original_size=12,
    processed_size=12,
    lines_shown=(1, 1),
    encoding: Optional[str] = "utf-8",
):
    return ProcessingResult(
        content=content,
        content_format=content_format,
        truncated=False,
        truncation_reason=None,
        original_size=original_size,
        processed_size=processed_size,
        lines_shown=lines_shown,
        file_type=file_type,
        encoding=encoding,
    )


def test_deduplicate_paths_normalizes_and_preserves_order():
    processor = FileMentionProcessor(session_id="session-1")
    paths = ["./foo.txt", "foo.txt", "bar/../foo.txt", "bar.txt", "bar.txt"]

    deduped = processor._deduplicate_paths(paths)

    assert deduped == ["foo.txt", "bar.txt"]


@pytest.mark.asyncio
async def test_read_file_safe_rejects_outside_workspace(monkeypatch, tmp_path):
    processor = FileMentionProcessor(session_id="session-1")

    monkeypatch.setattr(
        processor_module,
        "resolve_workspace_root",
        AsyncMock(return_value=tmp_path),
    )
    monkeypatch.setattr(
        processor_module,
        "validate_path_in_workspace",
        Mock(return_value=None),
    )

    result = await processor._read_file_safe("outside.txt")

    assert result.success is False
    assert result.error_message == "Path outside workspace: outside.txt"


@pytest.mark.asyncio
async def test_read_file_safe_handles_missing_file(monkeypatch, tmp_path):
    processor = FileMentionProcessor(session_id="session-1")
    missing_path = tmp_path / "missing.txt"

    monkeypatch.setattr(
        processor_module,
        "resolve_workspace_root",
        AsyncMock(return_value=tmp_path),
    )
    monkeypatch.setattr(
        processor_module,
        "validate_path_in_workspace",
        Mock(return_value=str(missing_path)),
    )
    monkeypatch.setattr(
        processor_module,
        "path_to_llm_format",
        Mock(side_effect=lambda path: str(path)),
    )

    result = await processor._read_file_safe("missing.txt")

    assert result.success is False
    assert result.error_message == f"File not found: {missing_path}"


def test_format_file_reminder_metadata_warning():
    processor = FileMentionProcessor(session_id="session-1")
    processing_result = _make_processing_result(
        "File is empty",
        content_format=ContentFormat.METADATA,
        file_type=FileType.TEXT,
        lines_shown=(0, 0),
    )
    file_content = FileContent(
        path="/workspace/empty.txt",
        processing_result=processing_result,
        success=True,
    )

    reminder = processor._format_file_reminder(file_content)

    assert "Called the Read tool" in reminder
    assert "Warning: File is empty" in reminder


def test_format_file_reminder_inline_data_fallback_when_no_multimodal(monkeypatch):
    processor = FileMentionProcessor(session_id="session-1")
    inline_content = {"inline_data": {"mime_type": "image/png", "data": "abc"}}
    processing_result = _make_processing_result(
        inline_content,
        content_format=ContentFormat.INLINE_DATA,
        file_type=FileType.IMAGE,
        original_size=2048,
        processed_size=3,
        lines_shown=(0, 0),
    )
    file_content = FileContent(
        path="/workspace/image.png",
        processing_result=processing_result,
        success=True,
    )

    monkeypatch.setattr(
        processor_module,
        "get_multimodal_support_for_session",
        Mock(return_value=False),
    )

    reminder = processor._format_file_reminder(file_content)

    assert "Cannot read image file" in reminder
    assert "multimodal content is not supported" in reminder


def test_format_file_reminder_inline_data_structured_for_multimodal(monkeypatch):
    processor = FileMentionProcessor(session_id="session-1")
    inline_content = {"inline_data": {"mime_type": "image/png", "data": "abc"}}
    processing_result = _make_processing_result(
        inline_content,
        content_format=ContentFormat.INLINE_DATA,
        file_type=FileType.IMAGE,
        original_size=2048,
        processed_size=3,
        lines_shown=(0, 0),
    )
    file_content = FileContent(
        path="/workspace/image.png",
        processing_result=processing_result,
        success=True,
    )

    monkeypatch.setattr(
        processor_module,
        "get_multimodal_support_for_session",
        Mock(return_value=True),
    )

    reminder = processor._format_file_reminder(file_content)

    assert isinstance(reminder, dict)
    reminder_dict = cast(Dict[str, Any], reminder)
    assert reminder_dict["type"] == "multimodal_file_mention"
    assert reminder_dict["parts"][0]["type"] == "text"
    assert reminder_dict["parts"][1]["inline_data"] == inline_content["inline_data"]


def test_format_file_reminder_text_escapes_quotes_and_backslashes():
    processor = FileMentionProcessor(session_id="session-1")
    processing_result = _make_processing_result(
        'line "value" \\ path',
        content_format=ContentFormat.TEXT,
        file_type=FileType.TEXT,
    )
    file_content = FileContent(
        path="/workspace/data.txt",
        processing_result=processing_result,
        success=True,
    )

    reminder = processor._format_file_reminder(file_content)

    expected = 'Result of calling the Read tool: "line \\"value\\" \\\\ path"'
    assert expected in reminder


@pytest.mark.asyncio
async def test_process_mentioned_files_deduplicates_and_skips_failures(monkeypatch):
    processor = FileMentionProcessor(session_id="session-1")
    success_content = FileContent(
        path="/workspace/a.txt",
        processing_result=_make_processing_result("content"),
        success=True,
    )
    failure_content = FileContent(
        path="/workspace/b.txt",
        processing_result=None,
        success=False,
        error_message="File not found",
    )

    async def fake_read(path):
        if path == "a.txt":
            return success_content
        return failure_content

    read_mock = AsyncMock(side_effect=fake_read)
    monkeypatch.setattr(processor, "_read_file_safe", read_mock)
    monkeypatch.setattr(processor, "_format_file_reminder", Mock(return_value="REMINDER"))

    mock_client = Mock()
    mock_client.tool_manager = Mock()
    mock_client.tool_manager._track_read_file = Mock()
    monkeypatch.setattr(
        session_client,
        "get_session_llm_client",
        Mock(return_value=mock_client),
    )

    result = await processor.process_mentioned_files(["./a.txt", "a.txt", "b.txt"])

    assert result == ["REMINDER"]
    assert read_mock.await_args_list == [
        call("a.txt"),
        call("b.txt"),
    ]
