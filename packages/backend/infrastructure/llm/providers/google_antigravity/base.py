"""
Antigravity base client.

Implements Code Assist API calls using OAuth tokens with endpoint fallback.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import secrets
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
from google.genai import types

from backend.config.dev import get_dev_config
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.retry import RateLimitError, run_with_retries, stream_with_retries
from backend.infrastructure.llm.shared.constants.thinking import GOOGLE_THINKING_LEVEL_TO_BUDGET
from backend.infrastructure.oauth.base.types import OAuthCredentials
from backend.infrastructure.oauth.google.oauth_client import DEFAULT_PROJECT_ID
from backend.infrastructure.oauth.google.token_manager import GoogleTokenManager
from backend.infrastructure.llm.providers.google.config import GoogleConfig
from backend.infrastructure.llm.providers.google_gemini_cli.context_manager import (
    GoogleGeminiCliContextManager,
)
from backend.infrastructure.llm.providers.google_gemini_cli.debug import GeminiCliDebugger
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor
from backend.infrastructure.llm.providers.google_antigravity.constants import (
    ANTIGRAVITY_ARCHES,
    ANTIGRAVITY_API_CLIENT,
    ANTIGRAVITY_CLIENT_METADATA,
    ANTIGRAVITY_SYSTEM_INSTRUCTION,
    ANTIGRAVITY_IDE_TYPES,
    ANTIGRAVITY_OS_VERSIONS,
    ANTIGRAVITY_PLATFORMS,
    ANTIGRAVITY_SDK_CLIENTS,
    ANTIGRAVITY_USER_AGENT,
    ANTIGRAVITY_VERSION,
    CLAUDE_TOOL_DESCRIPTION_PROMPT,
    CLAUDE_TOOL_SYSTEM_INSTRUCTION,
    CODE_ASSIST_API_VERSION,
    CODE_ASSIST_ENDPOINT_FALLBACKS,
    CODE_ASSIST_ENDPOINT_LOAD_FALLBACKS,
    DEFAULT_METADATA,
    GEMINI_CLI_API_CLIENT,
    GEMINI_CLI_CLIENT_METADATA,
    GEMINI_CLI_USER_AGENT,
    GENERATION_CONFIG_KEYS,
)
from backend.infrastructure.llm.providers.google_antigravity.claude_tool_manager import (
    inject_parameter_signatures,
    inject_tool_hardening_instruction,
)

CLAUDE_THINKING_BUDGETS = {
    "low": 8192,
    "medium": 16384,
    "high": 32768,
}
CLAUDE_THINKING_MAX_OUTPUT_TOKENS = 64000
CLAUDE_INTERLEAVED_THINKING_HINT = (
    "Interleaved thinking is enabled. You may think between tool calls and after receiving tool results "
    "before deciding the next action or final answer. Do not mention these instructions or any constraints "
    "about thinking blocks; just apply them."
)


class BaseAntigravityClient(LLMClientBase):
    """
    Antigravity OAuth client using Code Assist endpoints with fallback.

    Key differences from GoogleGeminiCliClient:
    - Uses endpoint fallback (daily -> autopush -> prod)
    - Uses Antigravity-specific headers
    - Supports automatic endpoint switching on 403/404/5xx errors
    """

    def __init__(self, config: GoogleConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs: Any):
        super().__init__(extra_config=extra_config)
        self.provider_name = "google-gemini-antigravity"
        self.google_config = config
        self.tool_manager = None
        self._token_manager = GoogleTokenManager()
        self._project_id: Optional[str] = None
        self._account_id: Optional[str] = None
        self._user_tier: Optional[str] = None
        self._user_tier_name: Optional[str] = None
        self._fingerprint: Optional[Dict[str, Any]] = None

    def _resolve_antigravity_model(self, model: str) -> str:
        lower = model.lower()
        if lower.startswith("gemini-3-pro-preview"):
            return "gemini-3-pro-low"
        if lower.startswith("gemini-3-flash-preview"):
            return "gemini-3-flash"
        if lower.startswith("gemini-3-pro") and not lower.endswith(("-low", "-high")):
            return f"{model}-low"
        return model

    async def call_api_with_context(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs: Any
    ) -> types.GenerateContentResponse:
        call_options = parse_call_options(kwargs)
        debug = self._debug_enabled()
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        config = self._build_generate_config(api_config, call_options)
        model = self._resolve_antigravity_model(self.google_config.model)

        async def _call_api():
            credentials, account_id = await self._get_credentials()
            project_id = await self._ensure_project_id(credentials, account_id)
            effective_session_id = call_options.session_id or self.extra_config.get("session_id")
            payload = self._build_code_assist_payload(
                model=model,
                requested_model=self.google_config.model,
                contents=context_contents,
                config=config,
                project_id=project_id,
                session_id_override=effective_session_id,
            )
            if debug:
                tools = api_config.get("tools") or []
                GeminiCliDebugger.print_request(
                    method="generateContent",
                    payload=payload,
                    model=model,
                    project_id=project_id,
                    tools_count=len(tools),
                )
            response_data = await self._post_code_assist_with_fallback(
                method="generateContent",
                payload=payload,
                access_token=credentials.access_token,
                timeout=timeout,
                debug=debug,
            )
            response = self._convert_code_assist_response(response_data)
            if not hasattr(response, "candidates") or not response.candidates:
                if debug:
                    print("[DEBUG] Gemini Antigravity returned empty candidates")
                raise Exception("Empty response (no candidates)")
            return response

        return await run_with_retries(
            _call_api,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        )

    async def call_api_with_context_streaming(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs: Any
    ) -> AsyncGenerator[StreamingChunk, None]:
        call_options = parse_call_options(kwargs)
        debug = self._debug_enabled()
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        config = self._build_generate_config(api_config, call_options)
        model = self._resolve_antigravity_model(self.google_config.model)
        processor = GoogleResponseProcessor.create_streaming_processor()

        async def _stream_once() -> AsyncGenerator[StreamingChunk, None]:
            credentials, account_id = await self._get_credentials()
            project_id = await self._ensure_project_id(credentials, account_id)
            effective_session_id = call_options.session_id or self.extra_config.get("session_id")
            payload = self._build_code_assist_payload(
                model=model,
                requested_model=self.google_config.model,
                contents=context_contents,
                config=config,
                project_id=project_id,
                session_id_override=effective_session_id,
            )
            if debug:
                tools = api_config.get("tools") or []
                GeminiCliDebugger.print_request(
                    method="streamGenerateContent",
                    payload=payload,
                    model=model,
                    project_id=project_id,
                    tools_count=len(tools),
                )

            async for event in self._stream_code_assist_with_fallback(
                method="streamGenerateContent",
                payload=payload,
                access_token=credentials.access_token,
                timeout=timeout,
                debug=debug,
            ):
                response = self._convert_code_assist_response(event)
                for chunk in processor.process_event(response):
                    yield chunk

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk

    def _get_response_processor(self) -> GoogleResponseProcessor:
        return GoogleResponseProcessor()

    def _get_context_manager_class(self):
        return GoogleGeminiCliContextManager

    def _get_provider_config(self) -> GoogleConfig:
        return self.google_config

    def _build_api_config(self, system_prompt: str, tool_schemas: Optional[List[Any]]) -> Dict[str, Any]:
        return {"system_prompt": system_prompt, "tools": tool_schemas}

    def _build_generate_config(self, api_config: Dict[str, Any], call_options: Any) -> types.GenerateContentConfig:
        kwargs_api = self.google_config.build_api_params()

        system_prompt = api_config.get("system_prompt", "")
        tool_schemas = api_config.get("tools", [])

        if system_prompt:
            kwargs_api["system_instruction"] = system_prompt
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

        resolved_model = self._resolve_antigravity_model(self.google_config.model)
        if resolved_model.startswith("gemini-3"):
            tier = "low"
            has_tier_suffix = False
            if resolved_model.endswith("-high"):
                tier = "high"
                has_tier_suffix = True
            elif resolved_model.endswith("-medium"):
                tier = "high"
                has_tier_suffix = True
            elif resolved_model.endswith("-minimal"):
                tier = "low"
                has_tier_suffix = True
            elif resolved_model.endswith("-low"):
                tier = "low"
                has_tier_suffix = True

            if not has_tier_suffix and call_options.thinking_level and call_options.thinking_level != "default":
                tier = call_options.thinking_level

            thinking_level = {
                "low": types.ThinkingLevel.LOW,
                "high": types.ThinkingLevel.HIGH,
            }.get(tier, types.ThinkingLevel.LOW)
            kwargs_api["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level, include_thoughts=True)
        elif call_options.thinking_level == "default":
            kwargs_api.pop("thinking_config", None)
        elif call_options.thinking_level is not None:
            model = self.google_config.model
            if model.startswith("gemini-2.5"):
                budget = GOOGLE_THINKING_LEVEL_TO_BUDGET.get(call_options.thinking_level, -1)
                kwargs_api["thinking_config"] = types.ThinkingConfig(thinking_budget=budget, include_thoughts=True)

        return types.GenerateContentConfig(**kwargs_api)

    async def _get_credentials(self) -> tuple[OAuthCredentials, str]:
        account_id_override = self.google_config.oauth_account_id or os.getenv("GOOGLE_OAUTH_ACCOUNT_ID")
        return await self._token_manager.get_credentials(account_id_override)

    async def _ensure_project_id(self, credentials: OAuthCredentials, account_id: str) -> Optional[str]:
        if self._project_id and self._account_id == account_id:
            return self._project_id

        project_id = credentials.project_id
        if project_id == DEFAULT_PROJECT_ID:
            project_id = None

        project_id = await self._resolve_project_id(credentials.access_token, project_id)
        self._project_id = project_id
        self._account_id = account_id
        return project_id

    async def _resolve_project_id(self, access_token: str, project_hint: Optional[str]) -> Optional[str]:
        env_project = (
            os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT_ID") or os.getenv("GCLOUD_PROJECT")
        )
        project_hint = project_hint or env_project

        load_res = await self._load_code_assist(access_token, project_hint)
        current_tier = load_res.get("currentTier") if isinstance(load_res, dict) else None

        project_id = self._extract_project_id(load_res)
        if current_tier:
            self._user_tier = current_tier.get("id") if isinstance(current_tier, dict) else None
            self._user_tier_name = current_tier.get("name") if isinstance(current_tier, dict) else None
            if project_id:
                return project_id
            if project_hint:
                return project_hint
            self._raise_project_required(load_res)

        allowed_tiers = load_res.get("allowedTiers") if isinstance(load_res, dict) else None
        tier = self._select_default_tier(allowed_tiers)
        if tier:
            onboard_res = await self._onboard_user(access_token, tier, project_hint)
            project_id = self._extract_project_id(onboard_res.get("response") if isinstance(onboard_res, dict) else {})
            if project_id:
                self._user_tier = tier.get("id")
                self._user_tier_name = tier.get("name")
                return project_id

        if project_hint:
            return project_hint

        self._raise_project_required(load_res)
        return None

    def _raise_project_required(self, load_res: Any) -> None:
        if isinstance(load_res, dict):
            ineligible = load_res.get("ineligibleTiers")
            if isinstance(ineligible, list):
                for tier in ineligible:
                    if isinstance(tier, dict) and tier.get("reasonCode") == "VALIDATION_REQUIRED":
                        url = tier.get("validationUrl") or ""
                        message = tier.get("reasonMessage") or "Account validation required"
                        if url:
                            raise ValueError(f"{message}. Visit {url}")
        raise ValueError("This account requires GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID to be set.")

    async def _load_code_assist(self, access_token: str, project_hint: Optional[str]) -> Dict[str, Any]:
        """Load Code Assist with endpoint fallback."""
        metadata = dict(DEFAULT_METADATA)
        if project_hint:
            metadata["duetProject"] = project_hint

        payload: Dict[str, Any] = {
            "metadata": metadata,
        }
        if project_hint:
            payload["cloudaicompanionProject"] = project_hint

        headers = self._build_load_headers(access_token)
        return await self._post_code_assist_with_fallback(
            method="loadCodeAssist",
            payload=payload,
            access_token=access_token,
            headers_override=headers,
            endpoints=CODE_ASSIST_ENDPOINT_LOAD_FALLBACKS,
        )

    async def _onboard_user(
        self, access_token: str, tier: Dict[str, Any], project_hint: Optional[str]
    ) -> Dict[str, Any]:
        tier_id = tier.get("id") if isinstance(tier, dict) else None
        metadata = dict(DEFAULT_METADATA)
        if project_hint:
            metadata["duetProject"] = project_hint

        payload: Dict[str, Any] = {
            "tierId": tier_id,
            "metadata": metadata,
        }
        if tier_id != "free-tier":
            payload["cloudaicompanionProject"] = project_hint

        lro = await self._post_code_assist_with_fallback(
            method="onboardUser",
            payload=payload,
            access_token=access_token,
        )

        if isinstance(lro, dict) and lro.get("done"):
            return lro

        name = lro.get("name") if isinstance(lro, dict) else None
        if not name:
            return lro

        for _ in range(60):
            await asyncio.sleep(5)
            op = await self._get_operation(name, access_token)
            if op.get("done"):
                return op

        return lro

    async def _get_operation(self, name: str, access_token: str) -> Dict[str, Any]:
        """Get operation status with endpoint fallback."""
        errors: List[str] = []

        headers = self._build_load_headers(access_token)
        for endpoint in CODE_ASSIST_ENDPOINT_LOAD_FALLBACKS:
            try:
                url = f"{endpoint}/{CODE_ASSIST_API_VERSION}/{name}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.ok:
                            return await response.json()
                        if response.status in (403, 404):
                            continue
                        error_text = await response.text()
                        errors.append(f"{endpoint}: {response.status} {error_text[:200]}")
            except Exception as e:
                errors.append(f"{endpoint}: {e}")

        raise ValueError(f"Code Assist operation failed on all endpoints: {'; '.join(errors)}")

    def _select_default_tier(self, tiers: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(tiers, list) or not tiers:
            return None
        for tier in tiers:
            if isinstance(tier, dict) and tier.get("isDefault"):
                return tier
        return tiers[0] if isinstance(tiers[0], dict) else None

    def _extract_project_id(self, data: Any) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        project = data.get("cloudaicompanionProject")
        if isinstance(project, str) and project:
            return project
        if isinstance(project, dict):
            project_id = project.get("id")
            if isinstance(project_id, str) and project_id:
                return project_id
        return None

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": ANTIGRAVITY_USER_AGENT,
            "X-Goog-Api-Client": ANTIGRAVITY_API_CLIENT,
            "Client-Metadata": ANTIGRAVITY_CLIENT_METADATA,
        }
        headers.update(self._build_fingerprint_headers())
        return headers

    def _build_load_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": GEMINI_CLI_USER_AGENT,
            "X-Goog-Api-Client": GEMINI_CLI_API_CLIENT,
            "Client-Metadata": GEMINI_CLI_CLIENT_METADATA,
        }

    def _build_fingerprint_headers(self) -> Dict[str, str]:
        fingerprint = self._get_fingerprint()
        return {
            "User-Agent": fingerprint["user_agent"],
            "X-Goog-Api-Client": fingerprint["api_client"],
            "Client-Metadata": json.dumps(fingerprint["client_metadata"], separators=(",", ":")),
            "X-Goog-QuotaUser": fingerprint["quota_user"],
            "X-Client-Device-Id": fingerprint["device_id"],
        }

    def _get_fingerprint(self) -> Dict[str, Any]:
        if self._fingerprint is None:
            self._fingerprint = self._generate_fingerprint()
        return self._fingerprint

    def _regenerate_fingerprint(self) -> None:
        self._fingerprint = self._generate_fingerprint()

    def _generate_fingerprint(self) -> Dict[str, Any]:
        platform_key = random.choice(["darwin", "win32", "linux"])
        arch = random.choice(ANTIGRAVITY_ARCHES)
        os_version = random.choice(ANTIGRAVITY_OS_VERSIONS.get(platform_key, ANTIGRAVITY_OS_VERSIONS["linux"]))

        if platform_key == "darwin":
            platform_label = "MACOS"
        elif platform_key == "win32":
            platform_label = "WINDOWS"
        elif platform_key == "linux":
            platform_label = "LINUX"
        else:
            platform_label = random.choice(ANTIGRAVITY_PLATFORMS)

        return {
            "device_id": str(uuid.uuid4()),
            "user_agent": f"antigravity/{ANTIGRAVITY_VERSION} {platform_key}/{arch}",
            "api_client": random.choice(ANTIGRAVITY_SDK_CLIENTS),
            "client_metadata": {
                "ideType": random.choice(ANTIGRAVITY_IDE_TYPES),
                "platform": platform_label,
                "pluginType": "GEMINI",
                "osVersion": os_version,
                "arch": arch,
                "sqmId": f"{{{str(uuid.uuid4()).upper()}}}",
            },
            "quota_user": f"device-{secrets.token_hex(8)}",
        }

    def _build_code_assist_payload(
        self,
        model: str,
        requested_model: str,
        contents: List[Dict[str, Any]],
        config: Any,
        project_id: Optional[str],
        session_id_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        if hasattr(config, "model_dump"):
            config_dump = config.model_dump(by_alias=True, mode="json", exclude_none=True)
        elif isinstance(config, dict):
            config_dump = dict(config)
        else:
            raise TypeError("Invalid generate config type")

        system_instruction = config_dump.pop("systemInstruction", None)
        cached_content = config_dump.pop("cachedContent", None)
        tools = config_dump.pop("tools", None)
        tool_config = config_dump.pop("toolConfig", None)
        labels = config_dump.pop("labels", None)
        safety_settings = config_dump.pop("safetySettings", None)

        generation_config = {k: config_dump[k] for k in GENERATION_CONFIG_KEYS if k in config_dump}

        resolved_model = self._resolve_antigravity_model(model)
        thinking_config = generation_config.get("thinkingConfig")
        if resolved_model.startswith("gemini-3") and isinstance(thinking_config, dict):
            thinking_level = thinking_config.get("thinkingLevel")
            if isinstance(thinking_level, str):
                thinking_config["thinkingLevel"] = thinking_level.lower()

        if self._is_claude_thinking_model(requested_model):
            self._apply_claude_thinking_config(generation_config, requested_model)

        payload_contents = [self._dump_content(content) for content in contents]
        if self._is_claude_model(requested_model):
            payload_contents = self._normalize_claude_contents(payload_contents)

        vertex_request: Dict[str, Any] = {
            "contents": payload_contents,
        }
        vertex_request["systemInstruction"] = self._inject_antigravity_system_instruction(system_instruction)
        if self._is_claude_thinking_model(requested_model):
            self._append_claude_thinking_hint(vertex_request["systemInstruction"])
        if cached_content is not None:
            vertex_request["cachedContent"] = cached_content
        if tools is not None:
            vertex_request["tools"] = tools
        if tool_config is not None:
            vertex_request["toolConfig"] = tool_config
        if tools is not None and "claude" in model.lower():
            vertex_request["tools"] = self._normalize_claude_tools(vertex_request.get("tools"))
            vertex_request["toolConfig"] = self._ensure_claude_tool_config(vertex_request.get("toolConfig"))
            vertex_request["tools"] = inject_parameter_signatures(
                vertex_request["tools"], CLAUDE_TOOL_DESCRIPTION_PROMPT
            )
            inject_tool_hardening_instruction(
                vertex_request["systemInstruction"], CLAUDE_TOOL_SYSTEM_INSTRUCTION
            )
        if labels is not None:
            vertex_request["labels"] = labels
        if safety_settings is not None and self._should_include_safety_settings(safety_settings, model):
            vertex_request["safetySettings"] = safety_settings
        if generation_config:
            vertex_request["generationConfig"] = generation_config

        payload: Dict[str, Any] = {
            "model": model,
            "request": vertex_request,
            "requestType": "agent",
            "userAgent": "antigravity",
            "requestId": f"agent-{uuid.uuid4()}",
        }
        if project_id:
            payload["project"] = project_id

        session_id = session_id_override or self.extra_config.get("session_id")
        if session_id:
            vertex_request["sessionId"] = session_id

        return payload

    def _normalize_system_instruction(self, system_instruction: Any) -> Any:
        if isinstance(system_instruction, str):
            return {
                "role": "user",
                "parts": [{"text": system_instruction}],
            }
        if hasattr(system_instruction, "model_dump"):
            return system_instruction.model_dump(by_alias=True, mode="json", exclude_none=True)
        return system_instruction

    def _ensure_claude_tool_config(self, tool_config: Any) -> Dict[str, Any]:
        config = tool_config if isinstance(tool_config, dict) else {}
        function_config = config.get("functionCallingConfig")
        if not isinstance(function_config, dict):
            function_config = {}
        function_config["mode"] = "VALIDATED"
        config["functionCallingConfig"] = function_config
        return config

    def _inject_antigravity_system_instruction(self, system_instruction: Any) -> Dict[str, Any]:
        # Normalize to dict structure
        if system_instruction is not None:
            normalized = self._normalize_system_instruction(system_instruction)
            if not isinstance(normalized, dict):
                normalized = {"role": "user", "parts": []}
        else:
            normalized = {"role": "user", "parts": []}

        # Ensure role and parts list exist
        normalized["role"] = "user"
        parts = normalized.get("parts") if isinstance(normalized.get("parts"), list) else []

        # Inject ANTIGRAVITY_SYSTEM_INSTRUCTION at the beginning
        if parts and isinstance(parts[0], dict) and isinstance(parts[0].get("text"), str):
            # Prepend to existing first text part
            parts[0]["text"] = f"{ANTIGRAVITY_SYSTEM_INSTRUCTION}\n\n{parts[0]['text']}"
        else:
            # Insert as new first part
            parts.insert(0, {"text": ANTIGRAVITY_SYSTEM_INSTRUCTION})

        normalized["parts"] = parts
        return normalized

    def _is_claude_model(self, model: str) -> bool:
        return False

    def _is_claude_thinking_model(self, model: str) -> bool:
        return False

    def _extract_claude_thinking_tier(self, model: str) -> Optional[str]:
        lower = model.lower()
        if lower.endswith("-thinking-low"):
            return "low"
        if lower.endswith("-thinking-medium"):
            return "medium"
        if lower.endswith("-thinking-high"):
            return "high"
        return None

    def _get_claude_thinking_budget(self, model: str) -> Optional[int]:
        if not self._is_claude_thinking_model(model):
            return None
        tier = self._extract_claude_thinking_tier(model) or "high"
        return CLAUDE_THINKING_BUDGETS.get(tier, CLAUDE_THINKING_BUDGETS["high"])

    def _apply_claude_thinking_config(self, generation_config: Dict[str, Any], model: str) -> None:
        budget = self._get_claude_thinking_budget(model)
        if budget is None:
            return

        generation_config["thinkingConfig"] = {
            "include_thoughts": True,
            "thinking_budget": budget,
        }

        max_tokens = generation_config.get("maxOutputTokens")
        if not isinstance(max_tokens, int) or max_tokens <= budget:
            generation_config["maxOutputTokens"] = CLAUDE_THINKING_MAX_OUTPUT_TOKENS

    def _append_claude_thinking_hint(self, system_instruction: Any) -> None:
        if not isinstance(system_instruction, dict):
            return

        parts = system_instruction.get("parts")
        if not isinstance(parts, list):
            system_instruction["parts"] = [{"text": CLAUDE_INTERLEAVED_THINKING_HINT}]
            return

        for index in range(len(parts) - 1, -1, -1):
            part = parts[index]
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    part["text"] = f"{text}\n\n{CLAUDE_INTERLEAVED_THINKING_HINT}"
                    return

        parts.append({"text": CLAUDE_INTERLEAVED_THINKING_HINT})

    def _should_include_safety_settings(self, safety_settings: Any, model: str) -> bool:
        resolved_model = self._resolve_antigravity_model(model)
        if "image" in resolved_model.lower():
            return True
        if not isinstance(safety_settings, list):
            return True

        for setting in safety_settings:
            if not isinstance(setting, dict):
                return True
            threshold = setting.get("threshold")
            if isinstance(threshold, dict):
                threshold = threshold.get("threshold")
            if threshold not in ("BLOCK_NONE", None, "HARM_BLOCK_THRESHOLD_UNSPECIFIED"):
                return True

        return False

    def _dump_content(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, types.Content):
            data = content.model_dump(by_alias=True, mode="json", exclude_none=True)
        else:
            validated = types.Content.model_validate(content)
            data = validated.model_dump(by_alias=True, mode="json", exclude_none=True)

        return self._sanitize_content(data)

    def _sanitize_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        parts = content.get("parts")
        if not isinstance(parts, list):
            return content

        sanitized_parts = []
        for part in parts:
            if not isinstance(part, dict):
                sanitized_parts.append(part)
                continue
            sanitized_parts.append(self._sanitize_part(part))

        content["parts"] = sanitized_parts
        return content

    def _sanitize_part(self, part: Dict[str, Any]) -> Dict[str, Any]:
        if "thought" not in part:
            return part

        next_part = dict(part)
        thought_value = next_part.pop("thought", None)

        has_payload = any(
            key in next_part
            for key in (
                "text",
                "functionCall",
                "functionResponse",
                "inlineData",
                "fileData",
                "executableCode",
                "codeExecutionResult",
            )
        )

        if not has_payload and thought_value:
            next_part["text"] = f"[Thought: {thought_value}]"

        return next_part

    def _normalize_claude_contents(self, contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return contents

    def _strip_gemini_thought_metadata(self, part: Dict[str, Any]) -> Dict[str, Any]:
        return part

    def _normalize_claude_tools(self, tools: Any) -> Any:
        return tools

    def _ensure_function_response_output(self, function_response: Dict[str, Any]) -> None:
        response = function_response.get("response")

        if response is None:
            function_response["response"] = {"output": "Tool execution completed."}
            return

        if isinstance(response, str):
            text = response.strip()
            function_response["response"] = {
                "output": text if text else "Tool execution completed.",
            }
            return

        if not isinstance(response, dict):
            function_response["response"] = {"output": str(response)}
            return

        output = response.get("output")
        if isinstance(output, str) and output.strip():
            return

        for key in ("content", "text", "message", "result"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                response["output"] = value
                return

        payload = {k: v for k, v in response.items() if k != "output"}
        if payload:
            try:
                response["output"] = json.dumps(payload, ensure_ascii=False)
            except Exception:
                response["output"] = str(payload)
            return

        response["output"] = "Tool execution completed."

    async def _post_code_assist_with_fallback(
        self,
        method: str,
        payload: Dict[str, Any],
        access_token: str,
        timeout: Optional[float] = None,
        debug: bool = False,
        headers_override: Optional[Dict[str, str]] = None,
        endpoints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """POST to Code Assist with endpoint fallback."""
        errors: List[str] = []
        rate_limit_message: Optional[str] = None
        rate_limit_retry_after: Optional[float] = None
        timeout_cfg = aiohttp.ClientTimeout(total=timeout) if timeout else None
        endpoint_list = endpoints or CODE_ASSIST_ENDPOINT_FALLBACKS

        for endpoint in endpoint_list:
            try:
                headers = headers_override or self._build_headers(access_token)
                if self._is_claude_thinking_model(str(payload.get("model", ""))):
                    headers["anthropic-beta"] = "interleaved-thinking-2025-05-14"
                url = f"{endpoint}/{CODE_ASSIST_API_VERSION}:{method}"

                async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.ok:
                            return await response.json()

                        # Check for rate limit
                        if response.status == 429:
                            payload_data = await self._read_error_payload(response)
                            retry_after = self._extract_retry_after(payload_data)
                            message = self._extract_error_message(payload_data)
                            rate_limit_message = message
                            if retry_after is not None:
                                rate_limit_retry_after = retry_after
                            errors.append(f"{endpoint}: 429 {message}")
                            if headers_override is None:
                                self._regenerate_fingerprint()
                            continue

                        # Try next endpoint on 403/404/5xx
                        if response.status in (403, 404) or response.status >= 500:
                            error_text = await response.text()
                            errors.append(f"{endpoint}: {response.status} {error_text[:200]}")
                            continue

                        # Other errors are fatal
                        payload_data = await self._read_error_payload(response)
                        raise ValueError(
                            f"Code Assist request failed: {response.status} {self._format_error_payload(payload_data)}"
                        )

            except RateLimitError:
                raise
            except ValueError:
                raise
            except Exception as e:
                errors.append(f"{endpoint}: {e}")

        if rate_limit_message:
            raise RateLimitError(
                f"Code Assist rate limited: {rate_limit_message}",
                retry_after=rate_limit_retry_after,
            )

        raise ValueError(f"Code Assist request failed on all endpoints: {'; '.join(errors)}")

    async def _stream_code_assist_with_fallback(
        self,
        method: str,
        payload: Dict[str, Any],
        access_token: str,
        timeout: Optional[float] = None,
        debug: bool = False,
        headers_override: Optional[Dict[str, str]] = None,
        endpoints: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream from Code Assist with endpoint fallback."""
        errors: List[str] = []
        rate_limit_message: Optional[str] = None
        rate_limit_retry_after: Optional[float] = None
        timeout_cfg = aiohttp.ClientTimeout(total=timeout) if timeout else None
        endpoint_list = endpoints or CODE_ASSIST_ENDPOINT_FALLBACKS

        for endpoint in endpoint_list:
            try:
                headers = headers_override or self._build_headers(access_token)
                url = f"{endpoint}/{CODE_ASSIST_API_VERSION}:{method}"

                async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                    async with session.post(
                        url,
                        headers=headers,
                        params={"alt": "sse"},
                        json=payload,
                    ) as response:
                        if not response.ok:
                            if response.status == 429:
                                payload_data = await self._read_error_payload(response)
                                retry_after = self._extract_retry_after(payload_data)
                                message = self._extract_error_message(payload_data)
                                rate_limit_message = message
                                if retry_after is not None:
                                    rate_limit_retry_after = retry_after
                                errors.append(f"{endpoint}: 429 {message}")
                                if headers_override is None:
                                    self._regenerate_fingerprint()
                                continue

                            if response.status in (403, 404) or response.status >= 500:
                                error_text = await response.text()
                                errors.append(f"{endpoint}: {response.status} {error_text[:200]}")
                                continue

                            payload_data = await self._read_error_payload(response)
                            raise ValueError(
                                f"Code Assist streaming failed: {response.status} {self._format_error_payload(payload_data)}"
                            )

                        buffer: List[str] = []
                        async for raw_line in response.content:
                            line = raw_line.decode("utf-8").rstrip("\r\n")
                            if not line:
                                if buffer:
                                    yield json.loads("\n".join(buffer))
                                    buffer = []
                                continue
                            if line.startswith("data:"):
                                buffer.append(line[5:].strip())

                        if buffer:
                            yield json.loads("\n".join(buffer))

                        return  # Success, don't try other endpoints

            except RateLimitError:
                raise
            except ValueError:
                raise
            except Exception as e:
                errors.append(f"{endpoint}: {e}")

        if rate_limit_message:
            raise RateLimitError(
                f"Code Assist rate limited: {rate_limit_message}",
                retry_after=rate_limit_retry_after,
            )

        raise ValueError(f"Code Assist streaming failed on all endpoints: {'; '.join(errors)}")

    def _debug_enabled(self) -> bool:
        return get_dev_config().debug_mode

    async def _read_error_payload(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        try:
            return await response.json()
        except Exception:
            text = await response.text()
            return {"_raw": text}

    def _format_error_payload(self, payload: Dict[str, Any]) -> str:
        if "_raw" in payload:
            return str(payload.get("_raw"))
        return json.dumps(payload)

    def _extract_error_message(self, payload: Dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return str(payload)
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)
        return self._format_error_payload(payload)

    def _extract_retry_after(self, payload: Dict[str, Any]) -> Optional[float]:
        if not isinstance(payload, dict):
            return None
        error = payload.get("error")
        if not isinstance(error, dict):
            return None

        details = error.get("details")
        if not isinstance(details, list):
            return None

        retry_after = None
        for detail in details:
            if not isinstance(detail, dict):
                continue
            detail_type = detail.get("@type")
            if detail_type == "type.googleapis.com/google.rpc.RetryInfo":
                retry_after = self._parse_duration(detail.get("retryDelay"))
            if detail_type == "type.googleapis.com/google.rpc.ErrorInfo":
                metadata = detail.get("metadata")
                if isinstance(metadata, dict):
                    retry_after = retry_after or self._parse_duration(metadata.get("quotaResetDelay"))

        return retry_after

    def _parse_duration(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if text.endswith("s"):
                text = text[:-1]
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _convert_code_assist_response(self, data: Dict[str, Any]) -> types.GenerateContentResponse:
        response_data = data.get("response") if isinstance(data, dict) else None
        if not response_data:
            response_data = data
        response = types.GenerateContentResponse.model_validate(response_data)
        trace_id = data.get("traceId") if isinstance(data, dict) else None
        if trace_id:
            response.response_id = trace_id
        return response
