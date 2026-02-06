"""
Claude Antigravity client.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from google.genai import types

from .base import BaseAntigravityClient
from .claude_tool_manager import ClaudeAntigravityToolManager


class ClaudeAntigravityClient(BaseAntigravityClient):
    """
    Claude Antigravity client using Code Assist endpoints.

    Adds Claude-specific payload normalization and thinking handling to align with
    Antigravity plugin behavior.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.provider_name = "google-claude-antigravity"
        self.tool_manager = ClaudeAntigravityToolManager()

    def _resolve_antigravity_model(self, model: str) -> str:
        lower = model.lower()
        if "claude" in lower and lower.endswith("-vertex"):
            model = model[:-7]
            lower = model.lower()
        if "claude" in lower and "thinking" in lower:
            if lower.endswith("-thinking-low"):
                return model[:-4]
            if lower.endswith("-thinking-medium"):
                return model[:-7]
            if lower.endswith("-thinking-high"):
                return model[:-5]
        return model

    def _is_claude_model(self, model: str) -> bool:
        return "claude" in model.lower()

    def _is_claude_thinking_model(self, model: str) -> bool:
        lower = model.lower()
        return "claude" in lower and "thinking" in lower

    def _sanitize_part(self, part: Dict[str, Any]) -> Dict[str, Any]:
        return part

    def _normalize_claude_contents(self, contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []

        response_ids_by_name: Dict[str, List[str]] = {}
        for content in contents:
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                function_response = part.get("functionResponse") or part.get("function_response")
                if not isinstance(function_response, dict):
                    continue
                response_id = function_response.get("id")
                if not isinstance(response_id, str) or not response_id:
                    response_id = str(uuid.uuid4())
                    function_response["id"] = response_id
                response_name = function_response.get("name")
                if isinstance(response_name, str) and response_name:
                    response_ids_by_name.setdefault(response_name, []).append(response_id)

        for content in contents:
            if not isinstance(content, dict):
                normalized.append(content)
                continue

            parts = content.get("parts")
            if not isinstance(parts, list):
                normalized.append(content)
                continue

            sanitized_parts = []
            all_function_responses = True
            has_non_thought_part = False

            for part in parts:
                if not isinstance(part, dict):
                    all_function_responses = False
                    has_non_thought_part = True
                    sanitized_parts.append(part)
                    continue

                if part.get("thought") is True:
                    continue

                has_non_thought_part = True
                next_part = self._strip_gemini_thought_metadata(part)

                text_value = next_part.get("text")
                if isinstance(text_value, str) and not text_value.strip():
                    next_part.pop("text", None)

                function_response = next_part.get("functionResponse") or next_part.get("function_response")
                if isinstance(function_response, dict):
                    self._ensure_function_response_output(function_response)
                    if "parts" in function_response:
                        function_response.pop("parts", None)
                else:
                    all_function_responses = False

                function_call = next_part.get("functionCall") or next_part.get("function_call")
                if isinstance(function_call, dict):
                    call_id = function_call.get("id")
                    if not isinstance(call_id, str) or not call_id:
                        call_name = function_call.get("name")
                        if isinstance(call_name, str) and call_name:
                            name_queue = response_ids_by_name.get(call_name) or []
                            if name_queue:
                                function_call["id"] = name_queue.pop(0)
                            else:
                                function_call["id"] = str(uuid.uuid4())
                        else:
                            function_call["id"] = str(uuid.uuid4())

                if next_part:
                    sanitized_parts.append(next_part)

            role = content.get("role")
            if has_non_thought_part and all_function_responses:
                role = "user"

            if sanitized_parts:
                normalized.append({**content, "role": role, "parts": sanitized_parts})

        return normalized

    def _strip_gemini_thought_metadata(self, part: Dict[str, Any]) -> Dict[str, Any]:
        next_part = dict(part)

        if "thought" in next_part:
            del next_part["thought"]
        if "thoughtSignature" in next_part:
            del next_part["thoughtSignature"]
        if "thinkingMetadata" in next_part:
            del next_part["thinkingMetadata"]

        metadata = next_part.get("metadata")
        if isinstance(metadata, dict):
            google_metadata = metadata.get("google")
            if isinstance(google_metadata, dict):
                if "thoughtSignature" in google_metadata:
                    del google_metadata["thoughtSignature"]
                if "thinkingMetadata" in google_metadata:
                    del google_metadata["thinkingMetadata"]

                if not google_metadata:
                    metadata.pop("google", None)

            if not metadata:
                next_part.pop("metadata", None)

        return next_part

    def _build_generate_config(self, api_config: Dict[str, Any], call_options: Any) -> types.GenerateContentConfig:
        # Get base config with standard parameter handling
        config = super()._build_generate_config(api_config, call_options)
        kwargs_api = config.model_dump(by_alias=True, mode="json", exclude_none=True)

        # Claude doesn't support thinking_config - remove it
        kwargs_api.pop("thinkingConfig", None)

        return types.GenerateContentConfig(**kwargs_api)
