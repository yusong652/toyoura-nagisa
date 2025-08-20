# Anthropic原生工具优化策略

## 背景

在分析Anthropic官方文档中的原生工具（如bash、text_editor）时，发现一个重要洞察：当使用Anthropic作为LLM provider时，使用原生工具可能比我们自建的MCP工具更高效和节省token。

## 关键发现

### 1. API设计高度相似

通过对比Anthropic官方的`text_editor_20250728`工具和我们的实现：

- **功能对应**：
  ```
  Anthropic原生: text_editor_20250728, str_replace_based_edit_tool, bash_20241022
  aiNagisa实现: read.py, edit.py, shell.py
  ```

- **行为模式匹配**：
  - cat -n格式输出（行号+tab+内容）
  - 2000行默认限制
  - 相同的错误处理逻辑
  - 精确的str_replace替换机制

### 2. 性能优势分析

**原生工具优势**：
- **Token效率**：无MCP协议包装开销
- **延迟更低**：直接集成在Anthropic API中
- **优化程度**：经过Anthropic专门优化

**当前MCP架构优势**：
- **统一性**：所有LLM provider使用相同工具接口
- **可扩展性**：易于添加新工具和新provider
- **一致性**：工具行为在不同provider间保持一致

### 3. Claude Code底层推测

根据我们的实现与Anthropic原生工具的高度相似性，推测：
**Claude Code底层很可能就是调用了Anthropic的原生工具**

这解释了为什么我们模仿Claude Code的行为时，结果与官方原生工具如此一致。

## 建议的混合策略

### 智能工具路由架构

```python
class AnthropicToolManager(BaseToolManager):
    # 原生工具映射
    NATIVE_TOOLS = {
        "read": "text_editor_20250728",
        "edit": "str_replace_based_edit_tool", 
        "bash": "bash_20241022"
    }
    
    def should_use_native_tool(self, tool_name: str) -> bool:
        """判断是否应该使用原生工具"""
        return tool_name in self.NATIVE_TOOLS
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False):
        # 1. 获取原生工具
        native_tools = self._get_anthropic_native_tools()
        
        # 2. 获取MCP工具（排除已有原生替代的）
        mcp_tools = await self._get_filtered_mcp_tools(session_id, agent_profile, debug)
        
        # 3. 合并返回
        return native_tools + mcp_tools
```

### 实施步骤

1. **Phase 1 - 核心工具迁移**
   - 优先迁移read、edit、bash等核心工具到原生版本
   - 保持MCP工具作为fallback

2. **Phase 2 - 性能测试**
   - 对比原生工具vs MCP工具的实际性能差异
   - 测量token使用量和响应延迟

3. **Phase 3 - 智能选择**
   - 实现provider感知的工具选择逻辑
   - Anthropic使用原生工具，其他provider使用MCP工具

### 兼容性保证

- **多Provider支持**：在Gemini、OpenAI等provider上仍使用MCP工具
- **功能一致性**：确保原生工具和MCP工具行为一致
- **渐进式迁移**：分阶段实施，降低风险

## 技术实现考虑

### 工具注册逻辑

```python
def get_anthropic_native_tools(self):
    """获取Anthropic原生工具配置"""
    return [
        {
            "name": "text_editor_20250728",
            "description": "Edit files using Anthropic's native text editor",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": ["view", "str_replace", "create"]},
                    "path": {"type": "string"},
                    # ... 其他参数
                }
            }
        }
        # ... 其他原生工具
    ]
```

### 工具过滤逻辑

```python
def _get_filtered_mcp_tools(self, session_id: str, agent_profile: str, debug: bool):
    """获取过滤后的MCP工具（排除已有原生替代的）"""
    all_mcp_tools = await self.get_standardized_tools(session_id, agent_profile, debug)
    
    # 排除有原生替代的工具
    filtered_tools = {
        name: tool for name, tool in all_mcp_tools.items()
        if not self.should_use_native_tool(name)
    }
    
    return filtered_tools
```

## 预期收益

1. **性能提升**：减少token使用量，降低API调用延迟
2. **成本优化**：原生工具的token效率更高
3. **用户体验**：更快的响应速度
4. **架构优化**：充分利用各provider的优势

## 风险控制

1. **功能验证**：确保原生工具功能完整性
2. **错误处理**：原生工具失败时的fallback机制
3. **测试覆盖**：全面测试不同工具组合的兼容性

## 结论

通过混合使用Anthropic原生工具和自建MCP工具，可以在保持架构灵活性的同时，最大化性能和成本效益。这是一个值得深入实施的优化方向。