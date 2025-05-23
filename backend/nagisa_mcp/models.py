from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List

class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="工具名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")

class ToolCallResponse(BaseModel):
    result: Any = Field(None, description="工具执行结果")
    error: Optional[str] = Field(None, description="错误信息（如有）")

class ToolSchema(BaseModel):
    name: str = Field(..., description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    parameters: Optional[Dict[str, Any]] = Field(None, description="参数说明")

class ToolListResponse(BaseModel):
    tools: List[ToolSchema] = Field(default_factory=list, description="工具列表") 