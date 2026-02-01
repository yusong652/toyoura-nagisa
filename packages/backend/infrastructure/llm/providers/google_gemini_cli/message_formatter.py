"""
Gemini CLI-specific message formatter.

Aligns tool response formatting with gemini-cli Code Assist behavior.
"""

from typing import Any, Dict, Optional, List

from backend.infrastructure.llm.providers.google.message_formatter import GoogleMessageFormatter


class GoogleGeminiCliMessageFormatter(GoogleMessageFormatter):
    """Formatter for Gemini CLI Code Assist tool responses."""

    @staticmethod
    def format_messages(messages: List[Any]) -> List[Dict[str, Any]]:
        """
        Format messages for Gemini CLI.

        Merges consecutive tool_result messages into a single user turn where
        all parts are functionResponse (gemini-cli requirement).
        """
        contents: List[Dict[str, Any]] = []
        pending_tool_parts: List[Any] = []

        for msg in messages:
            if msg is None:
                continue

            if getattr(msg, "role", None) == "user" and isinstance(getattr(msg, "content", None), list):
                content_items = msg.content
                tool_blocks = [
                    item for item in content_items if isinstance(item, dict) and item.get("type") == "tool_result"
                ]
                non_tool_blocks = [
                    item for item in content_items if not (isinstance(item, dict) and item.get("type") == "tool_result")
                ]

                if tool_blocks:
                    for block in tool_blocks:
                        pending_tool_parts.extend(GoogleGeminiCliMessageFormatter._format_tool_result_block(block))

                if non_tool_blocks:
                    if pending_tool_parts:
                        contents.append({"role": "user", "parts": pending_tool_parts})
                        pending_tool_parts = []

                    try:
                        non_tool_msg = msg.model_copy(update={"content": non_tool_blocks})
                    except Exception:
                        non_tool_msg = msg
                        non_tool_msg.content = non_tool_blocks

                    contents.extend(GoogleMessageFormatter.format_messages([non_tool_msg]))

                if tool_blocks:
                    continue

            if pending_tool_parts:
                contents.append({"role": "user", "parts": pending_tool_parts})
                pending_tool_parts = []

            contents.extend(GoogleMessageFormatter.format_messages([msg]))

        if pending_tool_parts:
            contents.append({"role": "user", "parts": pending_tool_parts})

        return contents

    @staticmethod
    def format_tool_result_for_context(
        tool_name: str,
        result: Any,
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from google.genai import types

        llm_content = result["llm_content"]
        content_parts = llm_content["parts"]

        text_parts = []
        inline_data_parts = []

        for part in content_parts:
            part_type = part["type"]

            if part_type == "inline_data":
                blob = GoogleMessageFormatter._process_inline_data(part)
                if blob:
                    inline_data_parts.append(types.Part(inline_data=blob))
            elif part_type == "text":
                text_content = part.get("text", "")
                if text_content:
                    text_parts.append(text_content)

        if result.get("status") == "error":
            response_data: Dict[str, Any] = {
                "error": {
                    "message": result.get("message") or "Tool execution failed",
                    "isError": True,
                }
            }
        else:
            response_data = {"output": "\n".join(text_parts)} if text_parts else {}

        if not response_data and inline_data_parts:
            response_data = {"output": f"Binary content provided ({len(inline_data_parts)} item(s))."}

        function_response = types.FunctionResponse(
            name=tool_name,
            response=response_data,
        )
        if tool_call_id:
            function_response.id = tool_call_id

        if inline_data_parts:
            function_response.parts = inline_data_parts

        parts = [types.Part(function_response=function_response)]

        return {
            "role": "user",
            "parts": parts,
        }

    @staticmethod
    def _format_tool_result_block(block: Dict[str, Any]) -> List[Any]:
        tool_name = block.get("tool_name", "unknown")
        tool_call_id = block.get("tool_use_id") or block.get("tool_call_id")
        llm_content = block.get("content") or {}

        if not isinstance(llm_content, dict) or "parts" not in llm_content:
            llm_content = {"parts": [{"type": "text", "text": str(llm_content)}]}

        result = {
            "status": "error" if block.get("is_error") else "success",
            "message": block.get("message"),
            "llm_content": llm_content,
        }

        formatted = GoogleGeminiCliMessageFormatter.format_tool_result_for_context(
            tool_name,
            result,
            tool_call_id=tool_call_id,
        )
        parts = formatted.get("parts") if isinstance(formatted, dict) else None
        return parts if isinstance(parts, list) else []
