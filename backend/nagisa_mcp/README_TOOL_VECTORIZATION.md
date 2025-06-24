# 工具向量化系统 (Tool Vectorization System)

## 概述

工具向量化系统是aiNagisa的一个新特性，它允许AI智能地发现和选择工具，而不是在每次请求时都传入所有可用的工具。这个系统通过以下方式工作：

1. **工具向量化**: 将所有工具函数存储到向量数据库中
2. **智能搜索**: 根据用户请求语义搜索相关工具
3. **静态注册**: 所有工具在启动时注册到MCP服务器
4. **智能发现**: 通过meta tool帮助LLM发现和使用相关工具
5. **轻量级工具请求**: 使用简化的prompt让LLM快速判断需要的工具类别

## 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Query    │───▶│  Meta Tool       │───▶│  Vectorized     │
│                 │    │  Search          │    │  Tool Database  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  MCP Server      │
                       │  (Static Tools)  │
                       └──────────────────┘
```

## 核心组件

### 1. ToolVectorizer (`tool_vectorizer.py`)

工具向量化器负责将函数转换为向量并存储到ChromaDB中。

**主要功能:**
- 提取函数信息（名称、文档、参数、返回类型）
- 创建工具描述文本用于向量化
- 语义搜索工具
- 按类别和标签过滤工具

**使用示例:**
```python
from nagisa_mcp.tool_vectorizer import ToolVectorizer

vectorizer = ToolVectorizer("tool_db")

def my_tool(param: str) -> str:
    """这是一个示例工具"""
    return f"Processed: {param}"

# 注册工具到向量数据库
tool_id = vectorizer.register_tool(
    func=my_tool,
    category="processing",
    tags=["example", "demo"],
    module_name="my_module"
)

# 搜索工具
tools = vectorizer.search_tools("example tool", n_results=5)
```

### 2. SmartToolManager (`smart_tool_manager.py`)

智能工具管理器协调工具向量化和MCP服务器管理。

**主要功能:**
- 管理工具注册表
- 处理工具使用统计
- 跟踪工具使用情况
- 清理未使用的工具

**注意**: 当前版本中，动态注册功能已预留但未启用，所有工具采用静态注册策略。

### 3. ToolRegistry (`tool_registry.py`)

工具注册器管理现有工具模块的配置和元数据。

**主要功能:**
- 定义工具模块配置
- 提供工具模块元数据
- 按类别和标签组织工具

**配置示例:**
```python
tool_modules = {
    'web_search': {
        'module_path': 'backend.nagisa_mcp.tools.web_search',
        'register_function': 'register_web_search_tools',
        'category': 'information',
        'tags': ['search', 'web', 'information'],
        'description': 'Web search and information retrieval tools'
    }
}
```

### 4. SmartMCPServer (`smart_mcp_server.py`)

智能MCP服务器集成了所有功能，提供完整的工具管理服务。

**主要功能:**
- 静态注册所有工具到MCP服务器
- 提供meta tool用于工具发现
- 处理用户请求并智能选择工具

## 轻量级工具发现机制

### 设计理念

传统的工具选择方法需要将大量工具定义传递给LLM，这会导致：
- 高token消耗
- 响应速度慢
- 上下文混乱

我们的轻量级机制通过以下方式解决这些问题：

1. **工具查询函数**: LLM通过调用meta tool来发现可用工具
2. **保持思维链**: LLM可以继续使用获取到的工具，思维链不会断掉
3. **静态注册**: 所有工具在启动时注册，避免动态注册的开销

### 正确的使用方式

LLM应该按照以下步骤使用工具：

1. **查询可用工具**: 使用meta tool搜索相关工具
2. **获取工具信息**: 通过搜索结果了解工具功能
3. **使用工具**: 直接调用已注册的工具完成任务
4. **解释过程**: 说明使用了什么工具以及为什么

### Prompt设计

```python
tool_discovery_prompt = """Tool Usage Instructions:

When you need to use tools to help with user requests, you should:

1. First, use the available meta tools to discover relevant tools:
   - Use search_tools_by_keywords() to find tools by keywords
   - Use get_available_tool_categories() to see all available categories

2. Available tool categories include:
   - utilities: basic tools (time, weather, location, etc.)
   - information: information retrieval (web search, queries, etc.)
   - communication: communication tools (email, contacts, etc.)
   - scheduling: schedule management (calendar, events, etc.)
   - development: development tools (code, file operations, etc.)
   - media: media tools (image generation, etc.)
   - location: location services (maps, places, etc.)
   - memory: memory management (storage, recall, etc.)

3. After discovering the right tools, use them to complete the user's request.

4. Always explain what tools you're using and why they're helpful for the task.

Example workflow:
- User asks for weather → Search for weather-related tools → Use weather tool → Provide results
- User asks to search for information → Search for search tools → Use search tool → Provide results
- User wants to chat → No tools needed, respond naturally

Remember: Use the meta tools first to discover available tools, then use those tools to help the user."""
```

### 工作流程

```
1. 用户发送请求
   ↓
2. LLM分析请求，确定是否需要工具
   ↓
3. 如果需要工具，LLM调用meta tool搜索相关工具
   ↓
4. 系统在向量数据库中搜索相关工具
   ↓
5. 返回工具信息给LLM
   ↓
6. LLM使用已注册的工具完成任务
   ↓
7. 返回结果给用户
```

## 工作流程

### 1. 初始化阶段
```
1. 创建SmartMCPServer实例
2. 静态注册所有工具到MCP服务器
3. 初始化ToolVectorizer用于工具搜索
4. 注册meta tool用于工具发现
```

### 2. 用户请求处理
```
1. 用户发送请求
2. LLM使用meta tool搜索相关工具
3. 在向量数据库中搜索相关工具
4. 返回工具信息给LLM
5. LLM使用已注册的工具完成任务
```

### 3. 工具使用
```
1. LLM直接调用已注册的工具
2. 更新工具使用统计
3. 定期清理未使用的工具
```

## 工具类别

系统预定义了以下工具类别：

- **utilities**: 基础工具（时间、天气、位置等）
- **information**: 信息检索（网络搜索、查询等）
- **communication**: 通信工具（邮件、联系人等）
- **scheduling**: 日程管理（日历、事件等）
- **development**: 开发工具（代码、文件操作等）
- **media**: 媒体工具（图像生成等）
- **location**: 位置服务（地图、地点等）
- **memory**: 记忆管理（存储、回忆等）

## 使用方法

### 1. 启动智能MCP服务器

```python
from nagisa_mcp.smart_mcp_server import mcp

# 服务器已在app.py中启动
# 所有工具已静态注册
```

### 2. 查询可用工具类别

```python
# 调用meta tool
result = mcp.get_available_tool_categories()
print(result["categories"])
```

### 3. 搜索相关工具

```python
# 按关键词搜索
result = mcp.search_tools_by_keywords(
    keywords="weather temperature",
    max_results=5
)

for tool in result["tools"]:
    print(f"- {tool['name']}: {tool['description']}")
```

### 4. 使用工具

```python
# 直接调用已注册的工具
result = mcp.get_current_time()
print(f"当前时间: {result['time']}")
```

## 测试

### 1. 工具搜索测试

```bash
cd backend
python -c "
from nagisa_mcp.tools.meta_tool.tool import search_tools_by_keywords
result = search_tools_by_keywords('weather', 3)
print(result)
"
```

### 2. 完整集成测试

```bash
cd backend
python -c "
from nagisa_mcp.smart_mcp_server import mcp
result = mcp.get_available_tool_categories()
print(result)
"
```

## 配置

### 环境变量

- `TOOL_DB_PATH`: 工具数据库路径（默认: "tool_db"）
- `MAX_TOOLS_PER_REQUEST`: 每次请求的最大工具数（默认: 5）

### 自定义工具注册

要添加新的工具模块，在 `smart_mcp_server.py` 中添加注册调用：

```python
from backend.nagisa_mcp.tools.my_new_module import register_my_new_tools

# 注册新工具
register_my_new_tools(mcp)
```

## 优势

1. **减少上下文负担**: 通过meta tool智能发现工具，减少token消耗
2. **提高响应速度**: 所有工具已预注册，无需动态加载
3. **更好的扩展性**: 新增工具自动加入向量空间
4. **智能发现**: 基于语义相似度发现最相关的工具
5. **稳定性**: 静态注册避免动态注册的复杂性
6. **轻量级决策**: 简化的prompt提高LLM响应速度
7. **标准化输出**: JSON格式确保解析可靠性

## 性能优化

### 1. 轻量级Prompt优化
- 使用低温度设置（0.1）确保一致性
- 简化的决策逻辑，只判断类别
- 强制JSON输出格式

### 2. 向量搜索优化
- 使用ChromaDB进行高效语义搜索
- 支持类别和标签过滤
- 缓存常用工具搜索结果

### 3. 内存管理
- 工具使用统计跟踪
- 定期清理向量数据库

## 未来改进

1. **LLM集成优化**: 进一步优化prompt和响应解析
2. **使用模式学习**: 基于历史使用模式优化工具选择
3. **工具组合**: 支持工具组合和依赖关系
4. **性能优化**: 优化向量搜索性能
5. **可视化界面**: 添加工具管理可视化界面
6. **多轮对话优化**: 支持对话上下文中的工具选择

## 注意事项

1. 首次启动时会注册所有工具模块
2. 工具向量化需要ChromaDB支持
3. 所有工具采用静态注册策略，确保稳定性
4. 建议定期清理向量数据库以节省空间
5. LLM工具请求需要配置正确的API密钥

## 故障排除

### 常见问题

1. **工具搜索无结果**
   - 检查工具描述是否足够详细
   - 确认搜索关键词是否合适
   - 验证向量数据库是否正确初始化

2. **MCP服务器错误**
   - 检查FastMCP版本兼容性
   - 确认工具函数签名正确
   - 验证工具注册是否成功

3. **LLM工具请求失败**
   - 检查API密钥配置
   - 确认LLM服务可用性
   - 检查prompt格式是否正确

### 调试模式

启用调试模式查看详细信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 测试工具搜索

```python
# 测试工具搜索功能
from nagisa_mcp.tools.meta_tool.tool import search_tools_by_keywords

def test_tool_search():
    result = search_tools_by_keywords("time weather", 3)
    print(f"搜索结果: {result}")
``` 