"""
Gemini Antigravity tool manager.
"""

from __future__ import annotations

from typing import Any, Dict, List

from google.genai import types

from backend.config.dev import get_dev_config
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema


class GoogleGeminiAntigravityToolManager(BaseToolManager):
    """Tool manager for Gemini Antigravity using Gemini-native schema types."""

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = "pfc_expert") -> List[Any]:
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if get_dev_config().debug_mode:
            print(
                "[DEBUG] GoogleGeminiAntigravityToolManager: "
                f"agent_profile={agent_profile}, tools_found={list(tools_dict.keys())}"
            )

        if not tools_dict:
            return []

        function_declarations = []
        for tool_schema in tools_dict.values():
            if not isinstance(tool_schema, ToolSchema):
                continue

            try:
                input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)
                json_schema_obj = types.JSONSchema(**input_schema_dict)
                gemini_schema = types.Schema.from_json_schema(json_schema=json_schema_obj)

                function_declarations.append(
                    types.FunctionDeclaration(
                        name=tool_schema.name,
                        description=tool_schema.description,
                        parameters=gemini_schema,
                    )
                )
            except Exception as exc:
                print(f"!!! [ERROR] Failed to convert tool {tool_schema.name} to Gemini Antigravity schema: {exc}")

        if not function_declarations:
            return []

        return [types.Tool(function_declarations=function_declarations)]
