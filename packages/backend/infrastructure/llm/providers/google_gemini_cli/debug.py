"""
Gemini CLI (Code Assist) debug utilities.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, Optional


class GeminiCliDebugger:
    """Debug utilities for Code Assist requests."""

    @staticmethod
    def print_request(
        *,
        method: str,
        payload: Dict[str, Any],
        model: str,
        project_id: Optional[str],
        tools_count: int,
    ) -> None:
        print("\n========== Gemini CLI Request ==========")
        print(f"method: {method}")
        print(f"model: {model}")
        print(f"project: {project_id or 'unknown'}")
        print(f"tools: {tools_count}")

        request = payload.get("request") if isinstance(payload, dict) else None
        if isinstance(request, dict):
            contents = request.get("contents")
            if isinstance(contents, list):
                print(f"contents: {len(contents)}")

            generation_config = request.get("generationConfig")
            config_parts = []
            if isinstance(generation_config, dict):
                temp = generation_config.get("temperature")
                if temp is not None:
                    config_parts.append(f"temp={temp}")
                max_tokens = generation_config.get("maxOutputTokens")
                if max_tokens is not None:
                    config_parts.append(f"max_tokens={max_tokens}")
                top_p = generation_config.get("topP")
                if top_p is not None:
                    config_parts.append(f"top_p={top_p}")
                top_k = generation_config.get("topK")
                if top_k is not None:
                    config_parts.append(f"top_k={top_k}")

                thinking_config = generation_config.get("thinkingConfig")
                if isinstance(thinking_config, dict):
                    level = thinking_config.get("thinkingLevel") or thinking_config.get("thinkingBudget")
                    if level is not None:
                        config_parts.append(f"thinking={level}")

            if config_parts:
                print(f"config: {', '.join(config_parts)}")

            system_instruction = request.get("systemInstruction")
            preview = GeminiCliDebugger._extract_system_preview(system_instruction)
            if preview:
                print(f"system: {preview}")

        payload_copy = GeminiCliDebugger._censor_payload(payload)
        print("payload (truncated):")
        GeminiCliDebugger._print_json(payload_copy)
        print("========== END ==========")

    @staticmethod
    def _censor_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        payload_copy = copy.deepcopy(payload)

        request = payload_copy.get("request")
        if not isinstance(request, dict):
            return payload_copy

        tools = request.get("tools")
        if isinstance(tools, list):
            request["tools"] = GeminiCliDebugger._truncate_tools(tools)

        contents = request.get("contents")
        if isinstance(contents, list):
            for content in contents:
                if not isinstance(content, dict):
                    continue
                GeminiCliDebugger._censor_parts(content.get("parts"))

        system_instruction = request.get("systemInstruction")
        if isinstance(system_instruction, dict):
            GeminiCliDebugger._censor_parts(system_instruction.get("parts"), max_len=100)

        return payload_copy

    @staticmethod
    def _truncate_tools(tools: list) -> list:
        result = []
        for tool in tools:
            if not isinstance(tool, dict):
                result.append(f"<{type(tool).__name__}>")
                continue

            tool_dict = tool.copy()
            truncated_tool: Dict[str, Any] = {}

            if tool_dict.get("googleSearch") is not None or tool_dict.get("google_search") is not None:
                truncated_tool["googleSearch"] = "<GoogleSearch>"

            if (
                tool_dict.get("googleSearchRetrieval") is not None
                or tool_dict.get("google_search_retrieval") is not None
            ):
                truncated_tool["googleSearchRetrieval"] = "<GoogleSearchRetrieval>"

            if tool_dict.get("codeExecution") is not None or tool_dict.get("code_execution") is not None:
                truncated_tool["codeExecution"] = "<CodeExecution>"

            declarations = tool_dict.get("functionDeclarations") or tool_dict.get("function_declarations")
            if declarations is not None:
                decls = []
                for func in declarations or []:
                    if isinstance(func, dict):
                        func_copy = func.copy()
                        if "description" in func_copy:
                            func_copy["description"] = GeminiCliDebugger._truncate(str(func_copy["description"]), 80)
                        if "parameters" in func_copy:
                            func_copy["parameters"] = {"properties": "..."}
                        decls.append(func_copy)
                    else:
                        decls.append(str(func))
                truncated_tool["functionDeclarations"] = decls

            if not truncated_tool:
                result.append({k: v for k, v in tool_dict.items() if v is not None})
            else:
                result.append(truncated_tool)

        return result

    @staticmethod
    def _extract_system_preview(system_instruction: Any) -> Optional[str]:
        if isinstance(system_instruction, str):
            cleaned = GeminiCliDebugger._truncate_system_reminder(str(system_instruction))
            return GeminiCliDebugger._truncate(cleaned, 80)

        if isinstance(system_instruction, dict):
            parts = system_instruction.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict):
                        text_value = part.get("text")
                        text_str = "" if text_value is None else str(text_value)
                        cleaned = GeminiCliDebugger._truncate_system_reminder(text_str)
                        return GeminiCliDebugger._truncate(cleaned, 80)

        return None

    @staticmethod
    def _censor_parts(parts: Any, max_len: Optional[int] = None) -> None:
        if not isinstance(parts, list):
            return

        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            text_str = "" if text is None else str(text)

            # Truncate system reminder first
            if "<system-reminder>" in text_str:
                text_str = GeminiCliDebugger._truncate_system_reminder(text_str)

            # Apply hard length limit if specified
            if max_len is not None and len(text_str) > max_len:
                text_str = f"{text_str[:max_len]}... [truncated {len(text_str)} chars]"

            part["text"] = text_str

            inline_data = part.get("inlineData")
            if isinstance(inline_data, dict):
                data = inline_data.get("data")
                if isinstance(data, str) and len(data) > 200:
                    inline_data["data"] = f"{data[:60]}... [truncated {len(data)} chars]"

            function_response = part.get("functionResponse")
            if isinstance(function_response, dict):
                nested_parts = function_response.get("parts")
                GeminiCliDebugger._censor_parts(nested_parts, max_len)

    @staticmethod
    def _print_json(obj: Any) -> None:
        try:
            print(json.dumps(obj, indent=2, ensure_ascii=False))
        except Exception:
            print(obj)

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return f"{text[: max_len - 3]}..."

    @staticmethod
    def _truncate_system_reminder(text: Optional[str]) -> str:
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        return re.sub(
            r"<system-reminder>[\s\S]*?</system-reminder>",
            "<system-reminder>... (truncated) ...</system-reminder>",
            text,
        )
