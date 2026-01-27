"""Helpers for tool parameter validation and schema generation."""

from __future__ import annotations

from functools import lru_cache
import inspect
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ConfigDict, create_model


class ToolParamsBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


def is_context_param(param: inspect.Parameter) -> bool:
    if param.name in {"context", "ctx"}:
        return True
    if param.annotation is inspect._empty:
        return False
    try:
        from backend.application.tools.context import ToolContext
    except Exception:
        return False
    return param.annotation is ToolContext


def get_context_param_name(handler: Callable[..., Any]) -> Optional[str]:
    signature = inspect.signature(handler)
    for param in signature.parameters.values():
        if is_context_param(param):
            return param.name
    return None


@lru_cache(maxsize=512)
def build_params_model(handler: Callable[..., Any]) -> type[BaseModel]:
    signature = inspect.signature(handler)
    fields: Dict[str, Any] = {}

    for param in signature.parameters.values():
        if is_context_param(param):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        annotation = param.annotation if param.annotation is not inspect._empty else Any
        default = param.default if param.default is not inspect._empty else ...
        fields[param.name] = (annotation, default)

    model_name = f"{getattr(handler, '__name__', 'Tool')}Params"
    return create_model(model_name, __base__=ToolParamsBase, **fields)


def build_input_schema(handler: Callable[..., Any]) -> Dict[str, Any]:
    return build_params_model(handler).model_json_schema(by_alias=True)


def get_tool_description(handler: Callable[..., Any]) -> str:
    return inspect.getdoc(handler) or "No description available"
