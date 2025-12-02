# Agent Abstraction Architecture Plan

## Overview

将 Nagisa 本体抽象成通用 Agent 对象，使主 Agent 和 SubAgent 共用同一套执行框架。这是一次架构升级，为未来更复杂的多 Agent 系统奠定基础。

## Design Philosophy

### 参考项目

1. **Gemini-CLI** (`_third_party/gemini-cli-src`)
   - 配置驱动的 `AgentDefinition`
   - `AgentExecutor` 执行循环
   - `SubagentToolWrapper` 将 Agent 包装成工具
   - 活动事件系统 (`SubagentActivityEvent`)

2. **LangGraph**
   - Supervisor 模式：主 Agent 分发任务给 SubAgent
   - 状态图驱动的工作流
   - 共享状态 vs 工具调用通信

### Core Principles

1. **配置驱动** - Agent 行为由配置对象定义，而非硬编码
2. **执行器复用** - 主 Agent 和 SubAgent 使用同一个 Executor
3. **活动可观测** - SubAgent 的执行进度可被父 Agent 和前端监听
4. **渐进迁移** - 可以先实现 SubAgent，再逐步重构主 Agent

---

## Architecture Design

### Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                              │
├─────────────────────────────────────────────────────────────┤
│  AgentDefinition    AgentResult    AgentActivity            │
│  (配置模型)          (结果模型)      (活动事件)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                           │
├─────────────────────────────────────────────────────────────┤
│  AgentExecutor              AgentRegistry                   │
│  (通用执行器)                (Agent 注册发现)                 │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ StreamingMode   │    │ NonStreamingMode│                 │
│  │ (主 Agent)      │    │ (SubAgent)      │                 │
│  └─────────────────┘    └─────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                          │
├─────────────────────────────────────────────────────────────┤
│  invoke_agent 工具    SubagentMonitor    WebSocket 通知     │
└─────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. AgentDefinition (Domain Model)

```python
# backend/domain/models/agent.py

from dataclasses import dataclass, field
from typing import Optional, List, Type
from pydantic import BaseModel

@dataclass
class AgentDefinition:
    """Agent 的完整配置定义 - 配置驱动设计"""

    # === 身份信息 ===
    name: str                          # 唯一标识符 (如 "nagisa_main", "pfc_explorer")
    display_name: str                  # 用户展示名
    description: str                   # 功能描述

    # === 提示配置 ===
    system_prompt: str                 # 系统提示模板 (支持 ${variable} 占位符)
    initial_messages: List[dict] = field(default_factory=list)  # Few-shot 示例

    # === 工具配置 ===
    tool_profile: str                  # 复用现有 ToolProfileManager

    # === 运行约束 ===
    max_iterations: int = 20           # 最大工具调用轮次
    timeout_seconds: int = 300         # 超时时间

    # === 输出配置 ===
    output_schema: Optional[Type[BaseModel]] = None  # Pydantic 验证 (SubAgent 用)

    # === 流式配置 ===
    streaming_enabled: bool = True     # 主 Agent 开启，SubAgent 关闭

    # === 上下文配置 ===
    inject_project_docs: bool = True   # 是否注入 CLAUDE.md 等项目文档
    enable_memory: bool = False        # 是否启用长期记忆 (SubAgent 通常关闭)
    enable_status_monitor: bool = True # 是否启用状态监控


@dataclass
class AgentResult:
    """Agent 执行结果"""
    status: str                        # "success", "error", "timeout", "max_iterations", "aborted"
    summary: str                       # 人类可读摘要
    data: Optional[dict] = None        # 结构化数据
    raw_response: Optional[str] = None # 原始 LLM 响应
    iterations_used: int = 0           # 使用的迭代次数


@dataclass
class AgentActivity:
    """Agent 活动事件 - 用于进度追踪和父 Agent 监听"""
    agent_name: str
    event_type: str                    # "tool_call_start", "tool_call_end", "thinking", "error"
    data: dict
    timestamp: float = field(default_factory=lambda: time.time())
```

#### 2. Predefined Agents

```python
# backend/domain/models/agent_definitions.py

from .agent import AgentDefinition
from .explorer_output import ExplorerResult

# === 主 Agent ===
NAGISA_MAIN = AgentDefinition(
    name="nagisa_main",
    display_name="Nagisa",
    description="主对话 Agent，处理用户的各种请求",
    system_prompt="${existing_system_prompt}",  # 复用现有系统提示
    tool_profile="general",
    max_iterations=64,
    streaming_enabled=True,
    inject_project_docs=True,
    enable_memory=True,
    enable_status_monitor=True,
)

# === PFC Explorer SubAgent ===
PFC_EXPLORER = AgentDefinition(
    name="pfc_explorer",
    display_name="PFC Explorer",
    description="PFC 文档查询和语法验证专用 Agent",
    system_prompt="""你是 PFC Explorer Agent，专门用于验证 PFC 语法和查询文档的子代理。

## 你的任务
${objective}

## 上下文
${context}

## 工作流程
1. 使用 pfc_query_command 查询命令语法
2. 使用 pfc_query_python_api 查询 Python API 用法
3. 如果需要验证，写一个最小测试脚本并执行
4. 返回验证后的、可工作的代码

## 规则
- 不要请求用户输入，独立解决问题
- 只报告经过验证的语法
- 输出使用结构化 JSON 格式""",
    tool_profile="pfc_explorer",
    max_iterations=10,
    timeout_seconds=120,
    streaming_enabled=False,
    output_schema=ExplorerResult,
    inject_project_docs=False,
    enable_memory=False,
    enable_status_monitor=False,
)

# === Agent 注册表 ===
AGENT_DEFINITIONS = {
    "nagisa_main": NAGISA_MAIN,
    "pfc_explorer": PFC_EXPLORER,
}
```

#### 3. AgentExecutor (Application Service)

```python
# backend/application/services/agent/executor.py

import asyncio
from typing import Optional, Callable, AsyncGenerator
from backend.domain.models.agent import AgentDefinition, AgentResult, AgentActivity
from backend.infrastructure.llm.base.client import LLMClientBase

class AgentExecutor:
    """
    通用 Agent 执行器

    核心职责:
    1. 构建初始上下文 (系统提示 + 文档注入)
    2. 执行对话循环 (LLM 调用 + 工具执行)
    3. 发射活动事件 (供父 Agent 和前端监听)
    4. 处理终止条件 (成功/超时/最大迭代/中止)
    """

    def __init__(
        self,
        definition: AgentDefinition,
        llm_client: LLMClientBase,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ):
        self.definition = definition
        self.llm_client = llm_client
        self.on_activity = on_activity
        self.tool_executor = ToolExecutor(...)  # 复用现有

    async def run(
        self,
        inputs: dict,                              # 模板变量 (如 {"objective": "...", "context": "..."})
        abort_signal: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """执行 Agent 对话循环"""

        start_time = asyncio.get_event_loop().time()
        iteration = 0

        # 1. 构建初始上下文
        system_prompt = self._render_template(self.definition.system_prompt, inputs)
        messages = await self._build_initial_messages(system_prompt, inputs)
        tools = await self._get_tools()

        # 2. 对话循环
        while iteration < self.definition.max_iterations:
            # 检查超时
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.definition.timeout_seconds:
                return AgentResult(
                    status="timeout",
                    summary=f"Agent 超时 ({self.definition.timeout_seconds}s)",
                    iterations_used=iteration,
                )

            # 检查中止信号
            if abort_signal and abort_signal.is_set():
                return AgentResult(
                    status="aborted",
                    summary="Agent 被用户中止",
                    iterations_used=iteration,
                )

            # LLM 调用
            if self.definition.streaming_enabled:
                response = await self._call_streaming(messages, tools)
            else:
                response = await self._call_non_streaming(messages, tools)

            # 发射活动事件
            self._emit_activity("llm_response", {"iteration": iteration})

            # 检查工具调用
            if not self._has_tool_calls(response):
                # 完成
                return self._finalize_result(response, iteration)

            # 执行工具
            tool_calls = self._extract_tool_calls(response)
            for tool_call in tool_calls:
                self._emit_activity("tool_call_start", {
                    "tool": tool_call.name,
                    "args": tool_call.args,
                })

            tool_results = await self.tool_executor.execute_all(tool_calls)

            for tool_call, result in zip(tool_calls, tool_results):
                self._emit_activity("tool_call_end", {
                    "tool": tool_call.name,
                    "status": result.status,
                })

            # 追加到消息
            messages.append(response)
            messages.append(self._format_tool_results(tool_results))

            iteration += 1

        # 达到最大迭代
        return AgentResult(
            status="max_iterations",
            summary=f"达到最大迭代次数 ({self.definition.max_iterations})",
            iterations_used=iteration,
        )

    def _render_template(self, template: str, inputs: dict) -> str:
        """渲染模板字符串，替换 ${variable} 占位符"""
        import re
        pattern = r'\$\{(\w+)\}'

        def replace(match):
            key = match.group(1)
            if key not in inputs:
                raise ValueError(f"Missing required input: {key}")
            return str(inputs[key])

        return re.sub(pattern, replace, template)

    def _emit_activity(self, event_type: str, data: dict):
        """发射活动事件"""
        if self.on_activity:
            activity = AgentActivity(
                agent_name=self.definition.name,
                event_type=event_type,
                data=data,
            )
            self.on_activity(activity)

    def _finalize_result(self, response, iteration: int) -> AgentResult:
        """处理最终响应"""
        # 如果有输出 schema，验证并解析
        if self.definition.output_schema:
            try:
                parsed = self._parse_structured_output(response)
                validated = self.definition.output_schema.model_validate(parsed)
                return AgentResult(
                    status="success",
                    summary=validated.summary if hasattr(validated, 'summary') else "完成",
                    data=validated.model_dump(),
                    iterations_used=iteration,
                )
            except Exception as e:
                return AgentResult(
                    status="error",
                    summary=f"输出验证失败: {e}",
                    raw_response=str(response),
                    iterations_used=iteration,
                )

        # 无 schema，直接返回
        return AgentResult(
            status="success",
            summary=self._extract_summary(response),
            raw_response=str(response),
            iterations_used=iteration,
        )
```

#### 4. AgentRegistry (Application Service)

```python
# backend/application/services/agent/registry.py

from typing import Optional, Dict
from backend.domain.models.agent import AgentDefinition
from backend.domain.models.agent_definitions import AGENT_DEFINITIONS

class AgentRegistry:
    """
    Agent 注册表

    管理所有可用的 Agent 定义，支持:
    1. 内置 Agent 加载
    2. 运行时 Agent 注册
    3. Agent 发现和查询
    """

    _instance: Optional['AgentRegistry'] = None

    def __init__(self):
        self._agents: Dict[str, AgentDefinition] = {}
        self._load_builtin_agents()

    @classmethod
    def get_instance(cls) -> 'AgentRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_builtin_agents(self):
        """加载内置 Agent 定义"""
        for name, definition in AGENT_DEFINITIONS.items():
            self._agents[name] = definition

    def register(self, definition: AgentDefinition):
        """运行时注册 Agent"""
        self._agents[definition.name] = definition

    def get(self, name: str) -> Optional[AgentDefinition]:
        """获取 Agent 定义"""
        return self._agents.get(name)

    def list_agents(self) -> list:
        """列出所有可用 Agent"""
        return [
            {
                "name": d.name,
                "display_name": d.display_name,
                "description": d.description,
            }
            for d in self._agents.values()
        ]
```

#### 5. invoke_agent Tool (Infrastructure)

```python
# backend/infrastructure/mcp/tools/agent/invoke_agent.py

from mcp import tool
from backend.application.services.agent.executor import AgentExecutor
from backend.application.services.agent.registry import AgentRegistry
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.shared.app_context import get_llm_client

@tool()
async def invoke_agent(
    agent_name: str,
    objective: str,
    context: str = "",
) -> dict:
    """
    调用指定的 Agent 执行任务。

    这是一个元工具，允许主 Agent 委托任务给专用 SubAgent。
    SubAgent 会独立执行，完成后返回结构化结果。

    Args:
        agent_name: Agent 名称 (如 "pfc_explorer")
        objective: 任务目标描述
        context: 附加上下文信息

    Returns:
        SubAgent 的执行结果，包含验证后的信息

    Example:
        invoke_agent(
            agent_name="pfc_explorer",
            objective="查询 ball create 命令的完整语法",
            context="用户需要创建 1000 个球体的模拟"
        )
    """
    # 获取 Agent 定义
    registry = AgentRegistry.get_instance()
    definition = registry.get(agent_name)

    if not definition:
        available = [a["name"] for a in registry.list_agents()]
        return error_response(
            f"未知的 Agent: {agent_name}。可用的 Agent: {available}"
        )

    # 创建执行器
    executor = AgentExecutor(
        definition=definition,
        llm_client=get_llm_client(),
        on_activity=_handle_subagent_activity,
    )

    # 执行
    result = await executor.run(
        inputs={
            "objective": objective,
            "context": context,
        }
    )

    # 格式化返回
    if result.status == "success":
        return success_response(
            message=f"{definition.display_name} 完成: {result.summary}",
            llm_content={"parts": [{"type": "text", "text": _format_findings(result)}]},
            agent_name=agent_name,
            iterations_used=result.iterations_used,
            findings=result.data,
        )
    else:
        return error_response(
            f"{definition.display_name} 失败 ({result.status}): {result.summary}"
        )


async def _handle_subagent_activity(activity: AgentActivity):
    """处理 SubAgent 活动事件 - 通知前端"""
    from backend.infrastructure.websocket.notification_service import notify_subagent_event
    await notify_subagent_event(activity)


def _format_findings(result: AgentResult) -> str:
    """格式化 Agent 结果为 LLM 可读内容"""
    if result.data:
        import json
        return f"## {result.summary}\n\n```json\n{json.dumps(result.data, indent=2, ensure_ascii=False)}\n```"
    return result.raw_response or result.summary
```

#### 6. Tool Profile Addition

```python
# backend/infrastructure/mcp/tool_profile_manager.py (修改)

class AgentProfile(Enum):
    # ... 现有 profiles ...
    PFC_EXPLORER = "pfc_explorer"  # 新增

# 在 TOOL_PROFILES 中添加
TOOL_PROFILES[AgentProfile.PFC_EXPLORER] = ToolProfile(
    name="PFC Explorer",
    description="PFC 文档查询和语法验证专用",
    tools=[
        "pfc_query_command",
        "pfc_query_python_api",
        "pfc_execute_task",
        "pfc_check_task_status",
        "bash",
        "read",
        "glob",
    ],
    estimated_tokens=2000,
    color="#9C27B0",
    icon="magnifying_glass",
)
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**目标**: 建立 Agent 抽象的基础设施

| Task | File | Priority |
|------|------|----------|
| 创建 AgentDefinition 模型 | `domain/models/agent.py` | P0 |
| 创建 AgentResult 模型 | `domain/models/agent.py` | P0 |
| 创建 AgentActivity 模型 | `domain/models/agent.py` | P0 |
| 定义 PFC_EXPLORER Agent | `domain/models/agent_definitions.py` | P0 |
| 添加 PFC_EXPLORER profile | `infrastructure/mcp/tool_profile_manager.py` | P0 |

### Phase 2: Executor (Week 1-2)

**目标**: 实现通用 Agent 执行器

| Task | File | Priority |
|------|------|----------|
| 实现 AgentExecutor 基础框架 | `application/services/agent/executor.py` | P0 |
| 实现模板渲染 | `application/services/agent/executor.py` | P0 |
| 实现非流式 LLM 调用 | `application/services/agent/executor.py` | P0 |
| 实现工具执行集成 | `application/services/agent/executor.py` | P0 |
| 实现活动事件发射 | `application/services/agent/executor.py` | P1 |
| 实现超时和中止处理 | `application/services/agent/executor.py` | P1 |

### Phase 3: Integration (Week 2)

**目标**: 将 Agent 系统集成到现有架构

| Task | File | Priority |
|------|------|----------|
| 实现 AgentRegistry | `application/services/agent/registry.py` | P0 |
| 实现 invoke_agent 工具 | `infrastructure/mcp/tools/agent/invoke_agent.py` | P0 |
| 注册工具到 MCP server | `infrastructure/mcp/smart_mcp_server.py` | P0 |
| 实现 WebSocket 通知 | `infrastructure/websocket/notification_service.py` | P1 |

### Phase 4: Testing & Polish (Week 3)

**目标**: 测试和完善

| Task | File | Priority |
|------|------|----------|
| 单元测试 AgentExecutor | `tests/agent/test_executor.py` | P0 |
| 集成测试 invoke_agent | `tests/agent/test_invoke_agent.py` | P0 |
| 端到端测试 PFC Explorer | `tests/agent/test_pfc_explorer.py` | P1 |
| 文档更新 | `CLAUDE.md` | P2 |

### Phase 5: Main Agent Migration (Future)

**目标**: 将主 Agent 也迁移到新架构 (可选)

| Task | Description | Priority |
|------|-------------|----------|
| 定义 NAGISA_MAIN Agent | 配置化主 Agent | P2 |
| 重构 ChatOrchestrator | 使用 AgentExecutor | P2 |
| 支持流式模式 | AgentExecutor 流式输出 | P2 |

---

## File Structure

```
packages/backend/
├── domain/
│   └── models/
│       ├── agent.py                    # AgentDefinition, AgentResult, AgentActivity
│       ├── agent_definitions.py        # 预定义 Agent (NAGISA_MAIN, PFC_EXPLORER)
│       └── explorer_output.py          # ExplorerResult Pydantic 模型
│
├── application/
│   └── services/
│       └── agent/
│           ├── __init__.py
│           ├── executor.py             # AgentExecutor
│           └── registry.py             # AgentRegistry
│
├── infrastructure/
│   ├── mcp/
│   │   ├── tools/
│   │   │   └── agent/
│   │   │       ├── __init__.py
│   │   │       └── invoke_agent.py     # invoke_agent 工具
│   │   └── tool_profile_manager.py     # 添加 PFC_EXPLORER profile
│   │
│   └── websocket/
│       └── notification_service.py     # 添加 subagent 事件通知
│
└── tests/
    └── agent/
        ├── test_executor.py
        ├── test_registry.py
        └── test_invoke_agent.py
```

---

## Key Design Decisions

### 1. 配置驱动 vs 继承

**选择**: 配置驱动 (AgentDefinition dataclass)

**理由**:
- 更灵活，易于运行时修改
- 避免类爆炸
- 与 Gemini-CLI 设计一致

### 2. Session 隔离 vs 共享

**选择**: 无 Session (纯函数式执行)

**理由**:
- SubAgent 是一次性任务，不需要持久状态
- 简化实现
- 与 Claude Code 的 Explore agent 行为一致

### 3. 流式 vs 非流式

**选择**: 可配置 (streaming_enabled)

**理由**:
- 主 Agent 需要流式 (用户体验)
- SubAgent 不需要 (简化实现，减少开销)

### 4. 工具执行复用

**选择**: 复用现有 ToolExecutor

**理由**:
- 工具执行逻辑已完善
- 保持一致性
- 减少重复代码

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 执行器与现有 ChatOrchestrator 冲突 | Low | Medium | 先独立实现，不修改现有代码 |
| SubAgent 性能问题 | Medium | Low | 设置严格的 timeout 和 max_iterations |
| 工具权限泄露 | Low | High | 严格的 tool_profile 白名单 |
| LLM 调用成本增加 | Medium | Medium | 默认使用更便宜的模型配置 |

---

## Success Metrics

1. **功能完整性**: invoke_agent 工具可以成功调用 PFC Explorer
2. **性能**: SubAgent 平均执行时间 < 30s
3. **可靠性**: SubAgent 成功率 > 90%
4. **可扩展性**: 新增 Agent 只需添加配置，无需修改执行器代码

---

## References

- Gemini-CLI Agent Architecture: `_third_party/gemini-cli-src/packages/core/src/agents/`
- LangGraph Documentation: https://blog.langchain.com/building-langgraph/
- 现有 PFC SubAgent 设计: `.claude/todos/pfc_subagent_design.md`
- 现有 ChatOrchestrator: `packages/backend/application/services/conversation/chat_orchestrator.py`

---

## Progress Tracking

### Last Updated: 2025-12-02

### Overall Status: 🟢 Phase 2 Completed, Phase 3 Ready

Phase 1-2 完成，可以开始 Phase 3 集成工作。

---

### ✅ Pre-requisites (Already Completed)

以下组件已经实现，可直接复用：

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| ToolProfileManager | `infrastructure/mcp/tool_profile_manager.py` | ✅ 完成 | 包含 `AgentProfile.PFC` |
| ToolExecutor | `application/services/conversation/tool_executor.py` | ✅ 完成 | 支持确认机制、级联阻塞 |
| PFC 工具集 | `infrastructure/mcp/tools/pfc/` | ✅ 完成 | 5 个工具全部实现 |
| ChatOrchestrator | `application/services/conversation/chat_orchestrator.py` | ✅ 完成 | 主 Agent 对话循环 |
| WebSocket 通知 | `infrastructure/websocket/notification_service.py` | ✅ 完成 | 工具结果通知已实现 |

---

### 📋 Phase 1: Foundation

**Status**: ✅ Completed (2025-12-02)
**Target**: 建立 Agent 抽象的基础设施

| Task | File | Status | Notes |
|------|------|--------|-------|
| 创建 AgentDefinition 模型 | `domain/models/agent.py` | ✅ | Pydantic BaseModel |
| 创建 AgentResult 模型 | `domain/models/agent.py` | ✅ | 包含 raw_response |
| 创建 AgentActivity 模型 | `domain/models/agent.py` | ✅ | 7 种事件类型 |
| 定义 PFC_EXPLORER Agent | `domain/models/agent_definitions.py` | ✅ | 基于 pfc profile |
| 定义 ExplorerResult 输出模型 | `domain/models/explorer_output.py` | ⏭️ | 跳过，初期不强制结构化输出 |

**Blockers**: None
**Decision**: 初期使用 raw_response 自然语言输出，后期按需添加 schema

---

### 📋 Phase 2: Executor

**Status**: ✅ Completed (2025-12-02)
**Target**: 实现通用 Agent 执行器

| Task | File | Status | Notes |
|------|------|--------|-------|
| 实现 AgentExecutor 基础框架 | `application/services/agent/executor.py` | ✅ | 包含完整执行循环 |
| 实现模板渲染 `_render_template` | `application/services/agent/executor.py` | ✅ | 支持 ${var} 占位符 |
| 实现非流式 LLM 调用 | `application/services/agent/executor.py` | ✅ | 使用 call_api_with_context |
| 工具执行集成 | `application/services/agent/executor.py` | ✅ | 直接用 tool_manager.handle_function_call |
| 实现活动事件发射 | `application/services/agent/executor.py` | ✅ | 7 种事件类型 |
| 实现超时和中止处理 | `application/services/agent/executor.py` | ✅ | 支持 abort_signal |

**Decision**: 不复用 ToolExecutor（它有确认机制），直接用 tool_manager

---

### 📋 Phase 3: Integration

**Status**: 🔴 Not Started
**Target**: 将 Agent 系统集成到现有架构

| Task | File | Status | Notes |
|------|------|--------|-------|
| 实现 AgentRegistry | `application/services/agent/registry.py` | ⬜ | P0 |
| 实现 invoke_agent 工具 | `infrastructure/mcp/tools/agent/invoke_agent.py` | ⬜ | P0 |
| 注册工具到 MCP server | `infrastructure/mcp/smart_mcp_server.py` | ⬜ | P0 |
| 扩展 WebSocket 通知支持 subagent 事件 | `infrastructure/websocket/notification_service.py` | ⬜ | P1 |

**Blockers**: Phase 2 必须先完成

---

### 📋 Phase 4: Testing & Polish

**Status**: 🔴 Not Started
**Target**: 测试和完善

| Task | File | Status | Notes |
|------|------|--------|-------|
| 单元测试 AgentExecutor | `tests/agent/test_executor.py` | ⬜ | P0 |
| 集成测试 invoke_agent | `tests/agent/test_invoke_agent.py` | ⬜ | P0 |
| 端到端测试 PFC Explorer | `tests/agent/test_pfc_explorer.py` | ⬜ | P1 |
| 文档更新 | `CLAUDE.md` | ⬜ | P2 |

**Blockers**: Phase 3 必须先完成

---

### 📋 Phase 5: Main Agent Migration (Future)

**Status**: 🔵 Deferred
**Target**: 将主 Agent 也迁移到新架构 (可选)

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| 定义 NAGISA_MAIN Agent | 配置化主 Agent | ⬜ | P2 |
| 重构 ChatOrchestrator | 使用 AgentExecutor | ⬜ | P2 |
| 支持流式模式 | AgentExecutor 流式输出 | ⬜ | P2 |

**Blockers**: Phase 4 完成后再评估是否需要

---

### Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not Started |
| 🟡 | In Progress |
| ✅ | Completed |
| 🔴 | Blocked |
| 🔵 | Deferred |

---

### Architecture Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-02 | 复用现有 `ToolExecutor` | 工具执行逻辑已完善，包含确认机制和级联阻塞 |
| 2025-12-02 | 基于现有 `AgentProfile.PFC` | 避免重复定义，直接扩展 |
| 2025-12-02 | 非流式优先 | SubAgent 不需要流式，简化实现 |
| 2025-12-02 | 跳过结构化输出 | 初期用 raw_response，后期按需添加 schema |
| 2025-12-02 | System prompt 固定化 | 不使用模板变量，任务通过 user message 传递 |
| 2025-12-02 | Messages 支持完整对话历史 | 主 Agent 重构后也使用此框架，需要普适性 |
| 2025-12-02 | 最大化基础设施复用 | 使用 `_prepare_complete_context()` 等现有方法 |

---

### Critical Design Principles

#### 1. Universal Architecture (普适性)

AgentExecutor 是**通用执行器**，未来主 Agent 也会重构到这套体系：

```
┌─────────────────────────────────────────────────────────┐
│                    AgentExecutor                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐      ┌─────────────────┐          │
│  │   SubAgent      │      │   Main Agent    │          │
│  │   (Explorer)    │      │   (Future)      │          │
│  │   - 单次任务     │      │   - 多轮对话     │          │
│  │   - 非流式       │      │   - 流式         │          │
│  └─────────────────┘      └─────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

#### 2. Message Structure (消息结构)

**关键**: 不假设单条消息，必须支持完整对话历史：

```python
# SubAgent 场景
messages = [
    {"role": "user", "content": "Find PFC ball syntax..."},  # 主 Agent 发送的任务
    {"role": "assistant", ...},                               # SubAgent 响应
    {"role": "user", "parts": [FunctionResponse(...)]},       # 工具结果
    ...
]

# Main Agent 场景 (未来)
messages = [
    {"role": "user", "content": "用户消息 1"},
    {"role": "assistant", "content": "助手回复 1"},
    {"role": "user", "content": "用户消息 2"},
    ...  # 完整多轮对话历史
]
```

#### 3. Prompt Architecture (提示架构)

```
┌─────────────────────────────────────┐
│ System Prompt (固定)                │  ← 定义角色、工作流、规则
│ - 无模板变量 ${...}                 │  ← 不含动态内容
│ - 存储在 AgentDefinition           │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ Messages[0] (动态)                  │  ← 第一条 user message
│ - 主 Agent 发送的任务指令            │  ← objective + context
│ - 或用户的实际消息                   │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ Messages[1:] (对话历史)             │  ← 后续对话
│ - assistant 响应                    │
│ - 工具调用结果                       │
└─────────────────────────────────────┘
```

#### 4. Infrastructure Reuse (基础设施复用)

**原则**: 最大化复用现有 LLM 基础设施层代码

| 操作 | 委托给 | 方法 |
|------|--------|------|
| API 配置构建 | LLMClient | `_prepare_complete_context()` |
| 消息格式化 | ContextManager | `get_working_contents()` |
| 工具 Schema | ToolManager | `get_function_call_schemas()` |
| 响应解析 | ResponseProcessor | `extract_text_content()`, `extract_tool_calls()` |

**禁止**: 在 AgentExecutor 中重复实现 provider-specific 逻辑

---

### Next Steps

1. **开始 Phase 1**: 创建 `domain/models/agent.py` 定义核心模型
2. **创建目录结构**: `application/services/agent/` 和 `infrastructure/mcp/tools/agent/`
3. **设计 ExplorerResult**: 确定 PFC Explorer 的输出格式
