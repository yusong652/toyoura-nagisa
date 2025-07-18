# FastMCP 工具 SOTA 标准

## 🎯 核心原则

FastMCP 工具的参数描述直接传递给 LLM 作为工具 schema，因此需要特别优化的提示词工程实践。

## 📝 SOTA 标准模板

### 1. 导入和基础结构

```python
from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field
from backend.nagisa_mcp.utils.tool_result import ToolResult

def tool_name(
    param: str = Field(..., description="[核心描述] (e.g., '[具体例子1]', '[具体例子2]', '[具体例子3]')"),
    context: Context
) -> Dict[str, Any]:
    """
    [一句话功能描述]
    
    [一句话详细说明，突出关键特性]
    """
```

### 2. 参数描述的提示词工程最佳实践

#### ✅ 优秀的 Field 描述

```python
# 搜索类工具
query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')")

# 邮件类工具
subject: str = Field(..., description="Email subject line that clearly summarizes the message content (e.g., 'Project Update - Q1 Results', 'Meeting Request for Tomorrow', 'Important: System Maintenance Notice')")

# 时间类工具
date: str = Field(..., description="Date in YYYY-MM-DD format or relative terms (e.g., '2025-01-20', 'today', 'next Monday', 'tomorrow')")

# 数量类工具
limit: int = Field(5, ge=1, le=20, description="Maximum number of results to return, between 1-20 (recommended: 5 for quick overview, 10 for detailed analysis)")
```

#### ❌ 避免的描述模式

```python
# 太简单，缺乏指导
query: str = Field(..., description="Search query")

# 太技术化，LLM 不需要知道实现细节
query: str = Field(..., description="The search query string that will be passed to the Google Search API via Gemini's grounding mechanism")

# 缺乏例子，LLM 难以理解期望的输入格式
date: str = Field(..., description="Date parameter")
```

### 3. 描述结构的最佳实践

#### 🎯 SOTA 结构模式

```
"[核心功能描述] (e.g., '[具体例子1]', '[具体例子2]', '[具体例子3]')"
```

**要素分解：**
1. **核心功能**：简洁明确地说明参数的用途
2. **具体例子**：提供 3 个不同场景的真实例子
3. **格式指导**：暗示期望的输入格式和风格

#### 📊 各类参数的 SOTA 模式

```python
# 1. 搜索查询
query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')")

# 2. 邮件地址
email: str = Field(..., description="Valid email address for the recipient (e.g., 'user@example.com', 'team@company.org', 'john.doe@gmail.com')")

# 3. 日期时间
date: str = Field(..., description="Date in YYYY-MM-DD format or natural language (e.g., '2025-01-20', 'today', 'next Monday', 'tomorrow')")

# 4. 文本内容
content: str = Field(..., description="Main text content or message body (e.g., 'Please review the attached document', 'Here are the meeting notes', 'Project status update')")

# 5. 数量限制
limit: int = Field(5, ge=1, le=20, description="Maximum number of results to return, between 1-20 (recommended: 5 for quick overview, 10 for detailed analysis)")

# 6. 可选参数
optional_param: str = Field(None, description="Optional parameter for additional filtering (e.g., 'high priority', 'urgent', 'follow-up required')")
```

### 4. 完整的 SOTA 示例

```python
def google_web_search(
    query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')"),
    context: Context
) -> Dict[str, Any]:
    """
    Search the web for current information using Google Search.
    
    Retrieves up-to-date information from the web with source citations
    and comprehensive response text for the given query.
    """
    # Implementation...
```

### 5. 提示词工程的高级技巧

#### 🧠 认知负载优化

```python
# 好：引导 LLM 理解参数的使用场景
query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')")

# 更好：还提供了时间性的暗示
query: str = Field(..., description="Search query to find current and up-to-date information on the web (e.g., 'latest AI developments January 2025', 'Python 3.12 new features', 'current news about climate change')")
```

#### 🎯 上下文感知优化

```python
# 针对不同工具类型的优化
# 搜索工具：强调"当前"和"最新"
query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')")

# 邮件工具：强调"专业"和"清晰"
subject: str = Field(..., description="Professional email subject line that clearly summarizes the message content (e.g., 'Project Update - Q1 Results', 'Meeting Request for Tomorrow', 'Important: System Maintenance Notice')")

# 计算工具：强调"精确"和"数学"
expression: str = Field(..., description="Mathematical expression to evaluate using standard arithmetic operations (e.g., '2 + 3 * 4', '(10 - 5) / 2', 'sqrt(16) + 2^3')")
```

### 6. 验证和测试

#### 🔍 质量检查清单

- [ ] 描述是否包含 3 个具体例子？
- [ ] 例子是否覆盖不同的使用场景？
- [ ] 描述是否指导了期望的输入格式？
- [ ] 是否避免了技术实现细节？
- [ ] 是否使用了积极的、指导性的语言？

#### 📊 A/B 测试建议

测试不同的描述风格对 LLM 工具使用质量的影响：

```python
# 版本 A：简洁版
query: str = Field(..., description="Search query for web information")

# 版本 B：SOTA 版
query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')")
```

**预期结果：SOTA 版本会产生更精确、更有用的工具调用。**

## 🎯 总结

FastMCP 工具的参数描述是直接面向 LLM 的提示词，需要：

1. **具体而非抽象**：提供真实的使用例子
2. **指导而非描述**：告诉 LLM 如何使用，而不是这是什么
3. **场景化**：包含不同使用场景的例子
4. **格式暗示**：通过例子暗示期望的输入格式

这种方法确保 LLM 能够更准确地理解和使用工具，提高整体系统的性能和用户体验。