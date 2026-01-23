from backend.domain.utils.content_filters import (
    strip_system_tags,
    unwrap_tags,
    filter_message_content,
)


def test_strip_system_tags_removes_tag_blocks():
    text = "Hello\n<system-reminder>internal\nline</system-reminder>\nWorld"

    assert strip_system_tags(text) == "Hello\n\nWorld"


def test_unwrap_tags_keeps_content():
    assert unwrap_tags("<error>File not found</error>") == "File not found"


def test_filter_message_content_string_removes_system_tags_and_unwraps():
    content = "hello<system-reminder>secret</system-reminder><error>oops</error>"

    assert filter_message_content(content) == "hellooops"


def test_filter_message_content_filters_blocks_and_tool_results():
    content = [
        {"type": "text", "text": "Hi <error>bad</error>"},
        {
            "type": "tool_result",
            "content": {"parts": [{"type": "text", "text": "<system-reminder>skip</system-reminder>ok"}]},
        },
    ]

    filtered = filter_message_content(content)

    assert filtered[0]["text"] == "Hi bad"
    tool_parts = filtered[1]["content"]["parts"]
    assert tool_parts[0]["text"] == "ok"
