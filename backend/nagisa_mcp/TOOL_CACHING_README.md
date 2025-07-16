# 工具缓存和动态工具选择功能

## 概述

我们实现了一个优雅的工具缓存和动态工具选择系统，实现了以下流程：

1. **用户消息** → 2. **LLM判断是否需要工具** → 3. **通过meta tool查询** → 4. **后端搜索相关工具** → 5. **缓存工具并返回给LLM** → 6. **LLM使用工具完成任务**

## 核心功能

### 1. 工具缓存机制

在 `AnthropicClient` 类中实现了会话级别的工具缓存：

```python
class AnthropicClient(LLMClientBase):
    def __init__(self, ...):
        # 工具缓存机制
        self.tool_cache = {}  # 缓存查询到的工具
        self.meta_tools = set()  # meta tool名称集合
        self.session_tool_cache = {}  # 按会话ID缓存工具
```

### 2. Meta Tool识别

系统能够识别meta tools并特殊处理：

```python
def _is_meta_tool(self, tool_name: str) -> bool:
    """判断是否为meta tool"""
    return tool_name in {
        "search_tools_by_keywords",
        "get_available_tool_categories", 
        "request_tools_for_task"
    }
```

### 3. 动态工具选择

`get_function_call_schemas()` 方法现在支持动态工具选择：

- **始终包含meta tools**：确保LLM始终能够查询工具
- **优先使用缓存工具**：如果有会话缓存的工具，优先返回
- **向后兼容**：如果没有缓存工具，返回所有工具

### 4. Meta Tool结果处理

在 `handle_function_call()` 中特殊处理meta tool调用：

```python
# 如果是search_tools_by_keywords，缓存查询到的工具
if tool_name == "search_tools_by_keywords" and session_id:
    # 提取并缓存工具
    extracted_tools = self._extract_tools_from_meta_result(meta_result)
    if extracted_tools:
        self._cache_tools_for_session(session_id, extracted_tools)
```

## 工作流程

### 1. 初始状态
- LLM获得所有工具（包括meta tools）
- 用户发送请求

### 2. 工具查询阶段
- LLM调用 `search_tools_by_keywords` 等meta tool
- 后端在向量数据库中搜索相关工具
- 系统缓存查询到的工具到会话缓存

### 3. 工具使用阶段
- 下一轮LLM调用时，`get_function_call_schemas()` 返回：
  - Meta tools（始终包含）
  - 缓存的工具（优先）
  - 其他工具（如果没有缓存）
- LLM使用获取到的工具完成任务

### 4. 缓存管理
- 按会话ID缓存工具
- 会话切换时可清理缓存
- 避免重复工具

## 接口变更

### LLM客户端接口

GeminiClient 的 `get_enhanced_response()` 方法接受 `session_id` 参数：

```python
async def get_enhanced_response(
    self,
    messages: List[BaseMessage],
    session_id: Optional[str] = None,
    **kwargs
) -> Tuple[BaseMessage, Dict[str, Any]]:
```

### 工具Schema获取

`get_function_call_schemas()` 方法现在支持会话ID：

```python
async def get_function_call_schemas(self, session_id: Optional[str] = None):
```

## 使用示例

### 1. 基本使用

```python
# 创建客户端
from backend.chat.llm_factory import get_client
client = get_client()  # 自动创建GeminiClient

# 发送消息（会自动处理工具缓存）
final_message, metadata = await client.get_enhanced_response(messages, session_id="session_123")
```

### 2. 手动缓存工具

```python
# 手动缓存工具
tools = [
    {
        "name": "get_current_time",
        "description": "Get current time",
        "category": "utilities",
        "parameters": {...}
    }
]
client._cache_tools_for_session("session_123", tools)
```

### 3. 清理缓存

```python
# 清理会话缓存
client._clear_session_tool_cache("session_123")
```

## 优势

1. **思维链连贯性**：LLM可以连续使用工具，保持上下文
2. **工具自由性**：动态选择最相关的工具
3. **性能优化**：避免每次都返回所有工具
4. **会话隔离**：不同会话的工具缓存相互独立
5. **向后兼容**：不影响现有功能

## 测试

运行测试文件验证功能：

```bash
cd backend
python test_tool_caching.py
```

## 注意事项

1. **会话管理**：确保正确传递session_id
2. **缓存清理**：在会话切换时考虑清理缓存
3. **错误处理**：meta tool调用失败时不影响正常流程
4. **调试模式**：启用debug模式查看详细日志

## 未来改进

1. **缓存过期**：添加工具缓存过期机制
2. **工具评分**：基于使用频率优化工具选择
3. **批量操作**：支持批量工具查询和缓存
4. **持久化**：将工具缓存持久化到数据库 