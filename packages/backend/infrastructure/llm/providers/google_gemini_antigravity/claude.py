"""
Claude Antigravity client.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from google.genai import types

from .base import BaseAntigravityClient
from .claude_tool_manager import GoogleClaudeAntigravityToolManager


class GoogleClaudeAntigravityClient(BaseAntigravityClient):
    """
    Claude Antigravity client using Code Assist endpoints.

    Adds Claude-specific payload normalization and thinking handling to align with
    Antigravity plugin behavior.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.provider_name = "google-claude-antigravity"
        self.tool_manager = GoogleClaudeAntigravityToolManager()

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
        kwargs_api = self.google_config.build_api_params()

        system_prompt = api_config.get("system_prompt", "")
        tool_schemas = api_config.get("tools", [])

        if system_prompt:
            kwargs_api["systemInstruction"] = system_prompt
        if tool_schemas:
            kwargs_api["tools"] = tool_schemas

        if call_options.temperature is not None:
            kwargs_api["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api["max_output_tokens"] = call_options.max_tokens
        else:
            kwargs_api.pop("max_output_tokens", None)
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k

        kwargs_api.pop("thinking_config", None)
        kwargs_api.pop("thinkingConfig", None)

        if "max_output_tokens" in kwargs_api:
            kwargs_api["maxOutputTokens"] = kwargs_api.pop("max_output_tokens")
        if "top_p" in kwargs_api:
            kwargs_api["topP"] = kwargs_api.pop("top_p")
        if "top_k" in kwargs_api:
            kwargs_api["topK"] = kwargs_api.pop("top_k")
        if "safety_settings" in kwargs_api:
            safety_settings = kwargs_api.pop("safety_settings")
            if isinstance(safety_settings, list):
                cleaned_settings = []
                for setting in safety_settings:
                    if hasattr(setting, "model_dump"):
                        cleaned_settings.append(setting.model_dump(by_alias=True, mode="json", exclude_none=True))
                    elif isinstance(setting, dict):
                        cleaned_settings.append(setting)
                safety_settings = cleaned_settings
            kwargs_api["safetySettings"] = safety_settings
        if "system_instruction" in kwargs_api:
            kwargs_api["systemInstruction"] = kwargs_api.pop("system_instruction")

        return types.GenerateContentConfig(**kwargs_api)
