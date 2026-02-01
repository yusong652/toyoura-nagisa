"""
Google Gemini CLI client.

Implements Code Assist (cloudcode-pa) API calls using OAuth tokens.
"""

from __future__ import annotations

import asyncio
import json
import os
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
from backend.infrastructure.llm.providers.google.context_manager import GoogleContextManager
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor
from backend.infrastructure.llm.providers.google.tool_manager import GoogleToolManager


CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
CODE_ASSIST_API_VERSION = "v1internal"

DEFAULT_METADATA = {
    "ideType": "IDE_UNSPECIFIED",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}

GENERATION_CONFIG_KEYS = {
    "temperature",
    "topP",
    "topK",
    "candidateCount",
    "maxOutputTokens",
    "stopSequences",
    "responseLogprobs",
    "logprobs",
    "presencePenalty",
    "frequencyPenalty",
    "seed",
    "responseMimeType",
    "responseSchema",
    "responseJsonSchema",
    "routingConfig",
    "modelSelectionConfig",
    "responseModalities",
    "mediaResolution",
    "speechConfig",
    "audioTimestamp",
    "thinkingConfig",
}


class GoogleGeminiCliClient(LLMClientBase):
    """Gemini CLI OAuth client using Code Assist endpoints."""

    def __init__(self, config: GoogleConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs: Any):
        super().__init__(extra_config=extra_config)
        self.provider_name = "google-gemini-cli"
        self.google_config = config
        self.tool_manager = GoogleToolManager()
        self._token_manager = GoogleTokenManager()
        self._project_id: Optional[str] = None
        self._account_id: Optional[str] = None
        self._user_tier: Optional[str] = None
        self._user_tier_name: Optional[str] = None

    async def call_api_with_context(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs: Any
    ) -> types.GenerateContentResponse:
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        config = self._build_generate_config(api_config, call_options)
        model = self.google_config.model

        async def _call_api():
            credentials, account_id = await self._get_credentials()
            project_id = await self._ensure_project_id(credentials, account_id)
            payload = self._build_code_assist_payload(
                model=model,
                contents=context_contents,
                config=config,
                project_id=project_id,
            )
            response_data = await self._post_code_assist(
                method="generateContent",
                payload=payload,
                access_token=credentials.access_token,
                timeout=timeout,
            )
            response = self._convert_code_assist_response(response_data)
            if not hasattr(response, "candidates") or not response.candidates:
                if debug:
                    print("[DEBUG] Gemini CLI returned empty candidates")
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
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        config = self._build_generate_config(api_config, call_options)
        model = self.google_config.model
        processor = GoogleResponseProcessor.create_streaming_processor()

        async def _stream_once() -> AsyncGenerator[StreamingChunk, None]:
            credentials, account_id = await self._get_credentials()
            project_id = await self._ensure_project_id(credentials, account_id)
            payload = self._build_code_assist_payload(
                model=model,
                contents=context_contents,
                config=config,
                project_id=project_id,
            )

            async for event in self._stream_code_assist(
                method="streamGenerateContent",
                payload=payload,
                access_token=credentials.access_token,
                timeout=timeout,
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
        return GoogleContextManager

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
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k

        if call_options.thinking_level == "default":
            kwargs_api.pop("thinking_config", None)
        elif call_options.thinking_level is not None:
            model = self.google_config.model
            if model.startswith("gemini-3"):
                thinking_level = {
                    "low": types.ThinkingLevel.LOW,
                    "high": types.ThinkingLevel.HIGH,
                }.get(call_options.thinking_level, types.ThinkingLevel.HIGH)
                kwargs_api["thinking_config"] = types.ThinkingConfig(
                    thinking_level=thinking_level, include_thoughts=True
                )
            elif model.startswith("gemini-2.5"):
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
        metadata = dict(DEFAULT_METADATA)
        if project_hint:
            metadata["duetProject"] = project_hint

        payload: Dict[str, Any] = {
            "metadata": metadata,
        }
        if project_hint:
            payload["cloudaicompanionProject"] = project_hint

        return await self._post_code_assist(
            method="loadCodeAssist",
            payload=payload,
            access_token=access_token,
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

        lro = await self._post_code_assist(
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
        url = f"{CODE_ASSIST_ENDPOINT}/{CODE_ASSIST_API_VERSION}/{name}"
        headers = self._build_headers(access_token)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"Code Assist operation failed: {response.status} {error_text}")
                return await response.json()

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
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "toyoura-nagisa/1.0",
            "X-Goog-Api-Client": "gl-python/toyoura-nagisa",
        }

    def _build_code_assist_payload(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        config: types.GenerateContentConfig,
        project_id: Optional[str],
    ) -> Dict[str, Any]:
        config_dump = config.model_dump(by_alias=True, mode="json", exclude_none=True)

        system_instruction = config_dump.pop("systemInstruction", None)
        cached_content = config_dump.pop("cachedContent", None)
        tools = config_dump.pop("tools", None)
        tool_config = config_dump.pop("toolConfig", None)
        labels = config_dump.pop("labels", None)
        safety_settings = config_dump.pop("safetySettings", None)

        generation_config = {k: config_dump[k] for k in GENERATION_CONFIG_KEYS if k in config_dump}

        payload_contents = [self._dump_content(content) for content in contents]

        vertex_request: Dict[str, Any] = {
            "contents": payload_contents,
        }
        if system_instruction is not None:
            vertex_request["systemInstruction"] = self._normalize_system_instruction(system_instruction)
        if cached_content is not None:
            vertex_request["cachedContent"] = cached_content
        if tools is not None:
            vertex_request["tools"] = tools
        if tool_config is not None:
            vertex_request["toolConfig"] = tool_config
        if labels is not None:
            vertex_request["labels"] = labels
        if safety_settings is not None:
            vertex_request["safetySettings"] = safety_settings
        if generation_config:
            vertex_request["generationConfig"] = generation_config

        payload: Dict[str, Any] = {
            "model": model,
            "user_prompt_id": str(uuid.uuid4()),
            "request": vertex_request,
        }
        if project_id:
            payload["project"] = project_id

        session_id = self.extra_config.get("session_id")
        if session_id:
            vertex_request["session_id"] = session_id

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

        # If part has no other payload, ensure text exists
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

    async def _post_code_assist(
        self,
        method: str,
        payload: Dict[str, Any],
        access_token: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        url = f"{CODE_ASSIST_ENDPOINT}/{CODE_ASSIST_API_VERSION}:{method}"
        headers = self._build_headers(access_token)
        timeout_cfg = aiohttp.ClientTimeout(total=timeout) if timeout else None

        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if not response.ok:
                    payload_data = await self._read_error_payload(response)
                    if response.status == 429:
                        retry_after = self._extract_retry_after(payload_data)
                        message = self._extract_error_message(payload_data)
                        raise RateLimitError(
                            f"Code Assist rate limited: {message}",
                            retry_after=retry_after,
                        )
                    raise ValueError(
                        f"Code Assist request failed: {response.status} {self._format_error_payload(payload_data)}"
                    )
                return await response.json()

    async def _stream_code_assist(
        self,
        method: str,
        payload: Dict[str, Any],
        access_token: str,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        url = f"{CODE_ASSIST_ENDPOINT}/{CODE_ASSIST_API_VERSION}:{method}"
        headers = self._build_headers(access_token)
        timeout_cfg = aiohttp.ClientTimeout(total=timeout) if timeout else None

        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(
                url,
                headers=headers,
                params={"alt": "sse"},
                json=payload,
            ) as response:
                if not response.ok:
                    payload_data = await self._read_error_payload(response)
                    if response.status == 429:
                        retry_after = self._extract_retry_after(payload_data)
                        message = self._extract_error_message(payload_data)
                        raise RateLimitError(
                            f"Code Assist rate limited: {message}",
                            retry_after=retry_after,
                        )
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
