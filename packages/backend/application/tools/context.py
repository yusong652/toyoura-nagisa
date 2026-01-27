from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ToolRequestMeta:
    client_id: str
    tool_call_id: str


@dataclass(frozen=True)
class ToolRequestContext:
    meta: ToolRequestMeta


@dataclass(frozen=True)
class ToolContext:
    client_id: str
    request_context: ToolRequestContext
    
    @property
    def session_id(self) -> str:
        return self.client_id
