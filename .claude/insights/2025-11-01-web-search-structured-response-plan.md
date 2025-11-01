# Web Search工具结构化响应改进计划

**日期**: 2025-11-01
**问题**: web_search工具目前返回LLM综合好的文本，而不是结构化的搜索结果

---

## 核心问题

### 当前架构的问题

```python
# 现在的flow（关注点分离错误）
User: "搜索ChromaDB架构"
  ↓
Agent: 调用 web_search 工具
  ↓
web_search工具:
  ├─ 调用LLM Provider的native search tool
  ├─ LLM内部综合信息（黑盒）
  └─ 返回综合后的response_text
  ↓
Agent: 收到已综合的文本，直接输出
```

**问题**：
1. **Infrastructure层越权**：搜索工具（基础设施层）做了信息综合（领域层的事）
2. **Agent失去控制权**：收到的是最终文本，无法自己决策如何使用搜索结果
3. **不符合Clean Architecture**：依赖倒置被破坏

### 理想的架构

```python
# 应该的flow
User: "搜索ChromaDB架构"
  ↓
Agent: 调用 web_search 工具
  ↓
web_search工具（Infrastructure层）:
  ├─ 执行搜索
  └─ 返回结构化数据：
      {
        "results": [
          {"title": "...", "url": "...", "snippet": "..."},
          {"title": "...", "url": "...", "snippet": "..."}
        ]
      }
  ↓
Agent（Domain层）:
  ├─ 分析这些结果
  ├─ 决定是否需要更多信息
  ├─ 综合信息（Agent的责任）
  └─ 生成答案
```

---

## 各Provider当前状态

| Provider | Native Search | Sources暴露 | 综合行为 | 实现状态 |
|----------|--------------|-------------|---------|---------|
| **Gemini** | ✅ google_search | ✅ groundingMetadata | 自动综合 | 已实现sources提取 |
| **Anthropic** | ✅ web_search_20250305 | ❌ **不暴露** | 自动综合 | sources=[] (API限制) |
| **OpenAI** | ❌ 无 | N/A | N/A | Placeholder |
| **Kimi** | ✅ $web_search | ⚠️ 未充分提取 | 自动综合 | 需改进 |
| **OpenRouter** | ❌ 无 | N/A | N/A | 依赖下游模型 |

**关键发现**：
- Gemini是唯一完全暴露sources的provider
- Anthropic的API设计决定了无法获取sources详情
- 其他provider需要独立搜索实现

---

## 改进方案

### 方案A：优化现有实现（短期，渐进式）

**目标**：在不破坏现有架构的情况下，最大化利用可用的结构化数据

#### 步骤1: 优化system prompt

```python
# backend/infrastructure/llm/shared/constants/prompts.py

DEFAULT_WEB_SEARCH_SYSTEM_PROMPT = (
    "You are a web search expert. Your role is to find information and present it in a structured way.\n\n"
    "When searching:\n"
    "1. Find relevant sources\n"
    "2. Present information WITH SOURCE ATTRIBUTION\n"
    "3. Clearly list what you found from each source\n"
    "4. Make source URLs and titles visible in your response\n\n"
    "Format your response with clear source citations."
)
```

**预期效果**：即使是Anthropic这种不暴露sources的provider，也会在文本中明确列出来源

#### 步骤2: 改进web_search.py的返回格式

```python
# backend/infrastructure/mcp/tools/builtin/web_search.py

# 当前（Line 73-81）
return success_response(
    message=f"Found {len(sources)} sources",
    llm_content={
        "parts": [{"type": "text", "text": response_text}]  # ← 只有综合文本
    },
    **search_result
)

# 改进后
return success_response(
    message=f"Found {len(sources)} sources",
    llm_content={
        "type": "search_results",
        "query": query,
        "sources": sources,  # ← 结构化sources
        "synthesis": response_text,  # ← 可选的综合文本
        "metadata": {
            "provider": llm_type,
            "timestamp": datetime.now().isoformat()
        }
    },
    sources=sources,  # data字段中也保留
    query=query,
    llm_type=llm_type
)
```

**优势**：
- Agent可以看到结构化sources
- 保留response_text作为参考
- Agent自己决定用哪个

#### 步骤3: 完善各provider的sources提取

**Gemini**：已实现（groundingMetadata），需验证完整性

**Anthropic**：添加方法但返回空+说明
```python
# backend/infrastructure/llm/providers/anthropic/response_processor.py

@staticmethod
def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Extract web search sources from Anthropic response.

    Note: Anthropic's web_search_20250305 tool does NOT expose individual
    source URLs in the API response. Search results are synthesized directly
    into the response text.

    Returns:
        Empty list (sources not available from Anthropic API)
    """
    if debug:
        print("[DEBUG] Anthropic web search does not expose source details in API response")
    return []
```

**Kimi**：研究API文档，看能否提取具体sources

**OpenAI/OpenRouter**：保持placeholder

---

### 方案B：自建独立搜索（中期，完全控制）

**动机**：摆脱对LLM Provider native tool的依赖

#### 实现独立搜索工具

```python
# backend/infrastructure/mcp/tools/builtin/independent_search.py

from duckduckgo_search import DDGS

async def independent_web_search(query: str, max_results: int = 10):
    """
    完全自主可控的搜索实现
    - 不依赖LLM provider
    - 返回纯结构化数据
    - 让Agent自己综合
    """
    results = DDGS().text(query, max_results=max_results)

    return success_response(
        message=f"Found {len(results)} results",
        llm_content={
            "type": "search_results",
            "query": query,
            "results": [
                {
                    "title": r['title'],
                    "url": r['href'],
                    "snippet": r['body']
                }
                for r in results
            ]
        }
    )
```

**优势**：
- ✅ 完全透明
- ✅ 无LLM综合（省token）
- ✅ Agent完全控制
- ✅ 免费（DuckDuckGo）

**劣势**：
- 需要额外依赖
- 需要时间实现和测试

---

## 实施计划

### Phase 1: 快速优化（明天）

1. **优化system prompt**（10分钟）
   - 修改 `DEFAULT_WEB_SEARCH_SYSTEM_PROMPT`
   - 强调结构化输出和source attribution

2. **改进web_search.py返回格式**（30分钟）
   - 修改 llm_content 结构
   - 同时包含 sources 和 synthesis
   - 保持向后兼容

3. **完善Anthropic response_processor**（20分钟）
   - 添加 `extract_web_search_sources` 方法
   - 返回空列表 + 文档说明API限制

### Phase 2: 深度改进（本周内）

4. **验证Gemini sources提取**（1小时）
   - 测试各种搜索场景
   - 确认 groundingMetadata 完整性
   - 处理边界情况

5. **研究Kimi API文档**（1小时）
   - 确认 $web_search 返回结构
   - 实现完整的sources提取
   - 或标注为"不支持详细sources"

### Phase 3: 独立实现（下周）

6. **实现independent_search工具**（2-3小时）
   - 使用 duckduckgo-search 库
   - 完整的错误处理
   - 缓存机制
   - 单元测试

7. **配置化选择**（1小时）
   - 让用户选择 native vs independent
   - 不同profile使用不同策略

---

## 技术债务记录

### 根本性问题

当前所有使用native tool的provider（Gemini, Anthropic, Kimi）都存在：
- **黑盒综合**：LLM在服务端自动综合信息
- **控制权缺失**：我们无法阻止这个综合过程
- **Token浪费**：即使我们不用综合结果，provider也做了

### 无法解决的限制

- **Anthropic**：API设计决定不暴露sources（只能接受）
- **所有native tools**：都会自动综合（只能忽略synthesis部分）

### 长期方向

逐步迁移到独立搜索实现，完全掌控：
1. 搜索过程
2. 结果格式
3. 综合逻辑
4. Token消耗

---

## 参考讨论

详见今天与用户的完整对话：
- LLM Provider native tool的内部机制推测
- Clean Architecture原则的违反分析
- 各provider的API限制对比
- "心虚"感的根源：核心服务不在掌控中

---

## 下一步行动

**明天**：
1. ✅ 复审这个计划
2. 执行 Phase 1 (快速优化)
3. 测试改进效果

**本周**：
- Phase 2 (深度改进)

**下周**：
- Phase 3 (独立实现) - 可选
