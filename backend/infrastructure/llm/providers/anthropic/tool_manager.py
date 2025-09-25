"""
Anthropic Tool Manager - 专门用于Anthropic API的工具管理器

继承自BaseToolManager，实现Anthropic特定的工具schema格式化和处理逻辑。
专门针对Anthropic Claude API的要求进行优化，包括input_schema格式化。
"""

from typing import Dict, Any, List, Optional

from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class AnthropicToolManager(BaseToolManager):
    """
    Anthropic专用工具管理器
    
    继承BaseToolManager的通用功能，并实现Anthropic特定的：
    - input_schema格式化
    - Anthropic tool对象构建
    - 参数描述和验证
    """
    
    def _format_schema_for_anthropic(self, tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化工具schema为Anthropic格式
        
        Args:
            tool_schema: 原始工具schema
            
        Returns:
            Dict: Anthropic格式的工具schema
        """
        input_schema = tool_schema.get("parameters", {"type": "object", "properties": {}})
        
        # 确保schema完整性
        if "properties" in input_schema:
            # 确保所有参数都有描述
            for prop in input_schema["properties"].values():
                if "description" not in prop:
                    prop["description"] = "Parameter value"
            
            # 保留原始的required字段，不要自动推断所有字段为必需
            # 如果原始schema没有required字段，说明所有字段都是可选的
            if "required" not in input_schema:
                input_schema["required"] = []  # 空数组表示所有字段都是可选的
        
        if "type" not in input_schema:
            input_schema["type"] = "object"
        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False
        
        return {
            "name": tool_schema["name"],
            "description": tool_schema.get("description", tool_schema["name"]),
            "input_schema": input_schema
        }
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> List[Dict[str, Any]]:
        """
        获取MCP工具的schema，返回Anthropic格式，支持agent profile过滤
        
        Args:
            session_id: 会话ID，用于工具缓存
            agent_profile: Agent profile名称，用于工具过滤
            debug: 是否启用调试输出
            
        Returns:
            List[Dict[str, Any]]: Anthropic格式的工具schema列表
        """
        
        # 使用基类的标准化工具获取方法
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)
        
        if not tools_dict:
            return []
        
        # 转换 ToolSchema 对象为 Anthropic 格式
        anthropic_tools = []
        for tool_name, tool_schema in tools_dict.items():
            # 将 JSONSchema 对象转换为字典
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)
            
            anthropic_tool = self._format_schema_for_anthropic({
                "name": tool_schema.name,
                "description": tool_schema.description,
                "parameters": input_schema_dict
            })
            anthropic_tools.append(anthropic_tool)
        
        if debug:
            print(f"[DEBUG] Final Anthropic tools count: {len(anthropic_tools)}")
        
        return anthropic_tools

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.
        
        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.
        
        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering
            debug: Whether to enable debug output
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in standardized dictionary format for system prompt
        """
        
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)
        
        if not tools_dict:
            return []
        
        # Convert ToolSchema objects to clean dictionary format for system prompt
        prompt_schemas = []
        for tool_name, tool_schema in tools_dict.items():
            try:
                # Build clean schema dictionary
                schema_dict = {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": tool_schema.inputSchema.model_dump(exclude_none=True)
                }
                prompt_schemas.append(schema_dict)
            except Exception as e:
                if debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue
        
        if debug:
            print(f"[DEBUG] Anthropic system prompt schemas count: {len(prompt_schemas)}")
        
        return prompt_schemas