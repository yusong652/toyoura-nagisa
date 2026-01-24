# P0: FastMCP解耦与内部工具系统重构

**Priority**: P0 (Critical Architecture Refactoring)
**Created**: 2026-01-25
**Status**: Planning
**Impact**: Foundation-level architecture change
**Estimated Effort**: 2-3 weeks

---

## 🎯 Executive Summary

当前toyoura-nagisa将FastMCP作为**内部工具执行通道**，带来跨进程耦合、IPC开销以及测试/调试成本，同时弱化了MCP作为“外部扩展协议”的角色。本重构目标是让**内部工具进程内直接调用**，并将FastMCP收敛为**外部工具接入/对外暴露**的可选组件。

---

## 🔴 核心问题

### 问题1: 循环耦合架构

**当前流程**：
```
Agent (主进程)
  ↓ ToolManager.call_tool()
MCP Client (主进程)
  ↓ IPC (SSE, port 9000)
MCP Server (独立进程)
  ↓ import toyoura-nagisa
Tool Implementation (主进程模块)
  ↓ 返回结果
回到Agent (主进程)
```

**问题**：
- ❌ **紧耦合**: MCP Server直接import同仓库代码，主进程又通过Client回调Server
- ❌ **本地IPC开销**: 调用本地逻辑仍需序列化→网络→反序列化
- ❌ **启动复杂度**: 需要额外进程与端口管理（9000）
- ❌ **测试困难**: 单元测试不得不启动MCP Server
- ❌ **调试复杂**: 堆栈跨越进程边界，问题定位更慢

### 问题2: 违背MCP协议设计初衷

**MCP协议的正确理解**（参考Claude Code、Cursor等项目）：

| 项目 | 内部工具 | MCP用途 |
|------|---------|---------|
| **Claude Code** | 直接实现 (Bash, Read, Edit) | 用户自定义外部工具 |
| **Cursor** | 内置函数调用 | 外部服务接入 |
| **Continue.dev** | 直接工具函数 | 可选MCP扩展 |
| **toyoura-nagisa (当前)** | ❌ 通过MCP Server | 无外部工具 |
| **toyoura-nagisa (目标)** | ✅ 直接调用 | 外部工具接入（可选） |

**MCP的正确定位**：
- ✅ **外部独立服务**的标准协议（如数据库工具、API服务）
- ✅ **用户自定义工具**的接入机制
- ❌ **不是**内部工具的实现方式

### 问题3: 分层职责边界不清

**当前工具定义位置**：`infrastructure/mcp/tools/`

**分层困惑**：
```
Infrastructure/MCP/Tools
    ↓ 调用
Application/Services
    ↓ 调用
Infrastructure (PFC Client, Shell Executor)
```

- ⚠️ Infrastructure依赖Application本身不违背DIP，但工具实现混合了协议适配、参数验证、业务编排、输出格式化
- ❌ 工具更像**Presentation/Adapter层**（类似API Controller），当前位置与职责错位
- ❌ ToolResult/ToolSchema等共用结构被放在mcp/utils下，导致应用层反向依赖mcp命名空间

---

## ✅ 解决方案：内部工具直接调用系统

### 新架构设计

**核心理念**：
- 内部工具 = 普通Python函数 + 装饰器注册
- 外部工具 = MCP Client接入（可选）

**目录结构**：
```
packages/backend/
├── application/
│   ├── tools/              # 内部工具实现（新增）
│   │   ├── base.py         # 工具装饰器、工具定义
│   │   ├── registry.py     # 全局工具注册中心
│   │   ├── pfc/
│   │   │   ├── execute_task.py
│   │   │   ├── check_task_status.py
│   │   │   ├── list_tasks.py
│   │   │   └── query_command.py
│   │   ├── coding/
│   │   │   ├── read.py
│   │   │   ├── write.py
│   │   │   ├── edit.py
│   │   │   ├── bash.py
│   │   │   ├── glob.py
│   │   │   └── grep.py
│   │   ├── agent/
│   │   │   └── invoke_agent.py
│   │   └── planning/
│   │       └── todo_write.py
│   └── services/           # 业务逻辑层（已存在）
│       ├── pfc/
│       │   └── task_execution_service.py
│       └── shell/
│           └── bash_execution_service.py
├── presentation/
│   ├── api/                # REST API
│   ├── websocket/          # WebSocket
│   └── mcp/                # (可选) MCP Server适配器，仅在对外暴露工具时启用
└── infrastructure/
    ├── llm/
    │   └── base/
    │       └── tool_manager.py  # 直接调用内部工具 + 外部MCP gateway
    ├── pfc/                # PFC Client实现
    ├── shell/              # Shell Executor实现
    └── mcp/                # 外部MCP接入（保留client/gateway/共用utils）
```

### 核心组件设计

#### 1. 工具装饰器系统 (`application/tools/base.py`)

```python
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class ToolDefinition:
    """工具定义（零外部依赖）"""
    name: str
    description: str
    parameters_schema: type[BaseModel]  # Pydantic for validation
    handler: Callable
    tags: set[str]
    category: str

    def to_llm_schema(self) -> Dict[str, Any]:
        """转换为LLM Function Calling格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema.model_json_schema()
        }

def tool(
    name: str,
    description: str,
    parameters: type[BaseModel],
    tags: set[str],
    category: str = "general",
):
    """工具装饰器（类似FastMCP，但更轻量）"""
    def decorator(func: Callable):
        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters,
            handler=func,
            tags=tags,
            category=category,
        )

        # 注册到全局注册表
        from backend.application.tools.registry import TOOL_REGISTRY
        TOOL_REGISTRY.register(tool_def)

        return func
    return decorator
```

#### 2. 全局工具注册表 (`application/tools/registry.py`)

```python
from typing import Dict, Optional
from backend.application.tools.base import ToolDefinition

class ToolRegistry:
    """全局工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool_def: ToolDefinition):
        """注册工具"""
        if tool_def.name in self._tools:
            raise ValueError(f"Tool already registered: {tool_def.name}")
        self._tools[tool_def.name] = tool_def

    def get(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)

    def get_by_category(self, category: str) -> Dict[str, ToolDefinition]:
        """按分类获取工具"""
        return {
            name: tool for name, tool in self._tools.items()
            if tool.category == category
        }

    def get_by_agent_profile(self, profile: str) -> Dict[str, ToolDefinition]:
        """按Agent配置获取工具"""
        from backend.domain.models.agent_profiles import get_tools_for_agent
        allowed = set(get_tools_for_agent(profile))
        return {
            name: tool for name, tool in self._tools.items()
            if name in allowed
        }

    def get_all(self) -> Dict[str, ToolDefinition]:
        """获取所有工具"""
        return self._tools.copy()

# 全局单例
TOOL_REGISTRY = ToolRegistry()
```

#### 3. 工具实现示例 (`application/tools/pfc/execute_task.py`)

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from backend.application.tools.base import tool

class ExecuteTaskParams(BaseModel):
    """参数模型（Pydantic验证）"""
    entry_script: str = Field(..., description="Path to PFC Python script")
    description: str = Field(..., description="Task description for tracking")
    run_in_background: bool = Field(True, description="Run in background mode")
    timeout: Optional[int] = Field(None, description="Timeout in milliseconds")

@tool(
    name="pfc_execute_task",
    description="Execute PFC simulation task with git version tracking",
    parameters=ExecuteTaskParams,
    tags={"pfc", "simulation", "python", "sdk"},
    category="pfc",
)
async def pfc_execute_task(
    session_id: str,  # Context injection by ToolManager
    params: ExecuteTaskParams
) -> Dict[str, Any]:
    """
    执行PFC任务（直接调用Application层服务，无MCP依赖）

    Args:
        session_id: Session context (injected by ToolManager)
        params: Validated parameters

    Returns:
        Standardized tool result dict with llm_content
    """
    from backend.application.services.pfc import get_pfc_task_execution_service

    # 调用业务逻辑层
    service = get_pfc_task_execution_service()
    result = await service.execute_task(
        session_id=session_id,
        script_path=params.entry_script,
        description=params.description,
        run_in_background=params.run_in_background,
        timeout=params.timeout,
    )

    # 返回标准格式（供LLM使用）
    return {
        "status": "success",
        "data": {
            "task_id": result.task_id,
            "entry_script": result.script_path,
            "git_commit": result.git_commit,
        },
        "llm_content": {
            "parts": [{"type": "text", "text": result.formatted_status}]
        }
    }
```

#### 4. ToolManager直接调用 (`infrastructure/llm/base/tool_manager.py`)

```python
class BaseToolManager:
    """工具管理器（直接调用，不再通过MCP）"""

    async def get_standardized_tools(
        self,
        session_id: str,
        agent_profile: str = "pfc_expert"
    ) -> Dict[str, ToolSchema]:
        """获取工具定义（不再通过MCP Client）"""
        from backend.application.tools.registry import TOOL_REGISTRY

        # 获取Agent允许的工具
        tools = TOOL_REGISTRY.get_by_agent_profile(agent_profile)

        # 转换为ToolSchema格式
        tool_schemas = {}
        for name, tool_def in tools.items():
            tool_schemas[name] = ToolSchema.from_tool_definition(tool_def)

        return tool_schemas

    async def call_tool(
        self,
        session_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_call_id: str = ""
    ) -> Dict[str, Any]:
        """直接调用工具（不再通过MCP Client）"""
        from backend.application.tools.registry import TOOL_REGISTRY

        # 获取内部工具定义
        tool_def = TOOL_REGISTRY.get(tool_name)
        if not tool_def:
            # 可选：转发到外部MCP工具
            from backend.infrastructure.mcp.gateway import get_external_tool_gateway
            gateway = get_external_tool_gateway()
            if gateway:
                return await gateway.call_tool(session_id, tool_name, tool_args, tool_call_id=tool_call_id)
            return {
                "status": "error",
                "message": f"Tool not found: {tool_name}"
            }

        try:
            # 参数验证（Pydantic）
            validated_params = tool_def.parameters_schema(**tool_args)

            # 直接调用工具函数（注入session_id）
            result = await tool_def.handler(
                session_id=session_id,
                params=validated_params
            )

            # 追踪read工具（用于edit前置检查）
            if tool_name == "read" and result.get("status") == "success":
                file_path = tool_args.get("path")
                if file_path:
                    self._track_read_file(session_id, file_path)

            return result

        except ValidationError as e:
            return {
                "status": "error",
                "message": f"Invalid parameters: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Tool execution failed: {e}"
            }
```

---

## 📋 迁移路径

### Phase 1: 内部工具系统实现（Week 1）

**目标**: 建立新工具系统，迁移核心工具

**任务清单**:
- [ ] 1.1 实现 `application/tools/base.py` (工具装饰器、ToolDefinition)
- [ ] 1.2 实现 `application/tools/registry.py` (全局注册表)
- [ ] 1.3 迁移简单工具（验证架构）:
  - [ ] `read.py` (文件读取，无复杂依赖)
  - [ ] `glob.py` (文件搜索)
  - [ ] `grep.py` (内容搜索)
- [ ] 1.4 提取 `ToolResult`/`ToolSchema` 共用结构到 shared（或明确保留在adapter）
- [ ] 1.5 扩展 `ToolSchema.from_tool_definition()`（替换from_mcp_tool路径）
- [ ] 1.6 更新 `ToolManager.call_tool()` 支持直接调用 + 外部MCP回退
- [ ] 1.7 单元测试（验证无需MCP Server即可测试）

**验收标准**:
- ✅ 工具可以不启动MCP Server直接调用
- ✅ 工具单元测试通过（无MCP依赖）
- ✅ 性能提升：消除本地IPC开销，工具调用为进程内直接调用

### Phase 2: 复杂工具迁移（Week 2）

**目标**: 迁移所有内部工具，提取业务逻辑到Service层

**任务清单**:
- [ ] 2.1 提取PFC工具业务逻辑:
  - [ ] `PfcTaskExecutionService` (从pfc_execute_task提取)
  - [ ] 迁移 `pfc_execute_task.py`
  - [ ] 迁移 `pfc_check_task_status.py`
  - [ ] 迁移 `pfc_list_tasks.py`
  - [ ] 迁移其他PFC工具
- [ ] 2.2 提取Bash工具业务逻辑:
  - [ ] 增强 `BashExecutionService`
  - [ ] 迁移 `bash.py`
  - [ ] 迁移 `bash_output.py`
- [ ] 2.3 迁移其他工具:
  - [ ] `write.py`, `edit.py`
  - [ ] `invoke_agent.py`
  - [ ] `todo_write.py`
  - [ ] `web_search.py`, `web_fetch.py`
- [ ] 2.4 集成测试（完整工具流程）

**验收标准**:
- ✅ 所有工具迁移完成
- ✅ 业务逻辑在Service层，工具层仅负责参数/输出适配
- ✅ 测试覆盖率 > 60%

### Phase 3: 解除默认依赖（Week 3）

**目标**: 停止默认启动MCP Server，保留外部工具接入能力（可选）

**任务清单**:
- [ ] 3.1 禁用默认MCP Server启动:
  - [ ] 将 `app.py` 中的MCP Server启动改为可配置/按需
  - [ ] 仅在外部MCP或对外暴露工具时启用Server
- [ ] 3.2 清理目录结构:
  - [ ] 迁移 `infrastructure/mcp/tools/` 到 `application/tools/`
  - [ ] 评估 `infrastructure/mcp/utils/` 的落点（shared或保留为adapter）
- [ ] 3.3 更新文档:
  - [ ] 更新 `CLAUDE.md` (架构说明)
  - [ ] 更新 `README.md` (移除MCP Server启动说明)
- [ ] 3.4 （可选）实现外部MCP工具加载器:
  - [ ] `infrastructure/mcp/gateway.py`（统一外部MCP调用）
  - [ ] 配置文件支持外部MCP Server URL

**验收标准**:
- ✅ 内部工具不依赖MCP Server（Server可选）
- ✅ 启动速度提升（默认不再启动额外进程）
- ✅ 文档更新完整
- ✅ （可选）外部工具加载器可用

---

## 📊 影响评估

### 架构改进

| 维度 | 当前 | 重构后 | 改进 |
|------|------|--------|------|
| **职责边界** | 工具=协议+业务混杂 | 内部工具/外部MCP分离 | 清晰可测 |
| **工具调用延迟** | ~10ms (IPC开销) | 进程内调用 | 明显降低 |
| **启动时间** | +MCP Server | 默认无需启动 | 启动更快 |
| **测试复杂度** | 需启动MCP Server | 直接测试工具函数 | 大幅简化 |

### 代码质量

| 指标 | 当前 | 目标 |
|------|------|------|
| 工具层代码复杂度 | 高（含业务逻辑） | 低（仅参数适配） |
| 业务逻辑位置 | 分散在工具中 | 集中在Service层 |
| 单元测试覆盖率 | ~10% | > 60% |
| 架构清晰度 | 4/10 (混乱) | 9/10 (清晰) |

### 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 迁移引入Bug | 高 | 中 | 完整测试覆盖，逐步迁移 |
| 性能回退 | 中 | 低 | 性能基准测试，进程内调用应更快 |
| 工具兼容性问题 | 中 | 低 | 保持工具接口不变，仅改实现 |
| 开发时间超期 | 中 | 中 | 分阶段实施，每阶段有验收标准 |

---

## 🎯 成功标准

### 必须达成 (P0)
- ✅ 所有内部工具通过直接调用实现（不通过MCP）
- ✅ 内部工具不再依赖MCP Server
- ✅ 工具调用性能明显提升（消除IPC）
- ✅ 单元测试无需启动MCP Server
- ✅ 架构符合Clean Architecture原则

### 应该达成 (P1)
- ✅ 业务逻辑提取到Service层
- ✅ 测试覆盖率 > 60%
- ✅ 文档更新完整

### 可以达成 (P2)
- ⭐ 外部MCP工具加载器实现
- ⭐ 性能监控和基准测试
- ⭐ 迁移文档和最佳实践指南

---

## 📚 参考资料

### 架构模式
- Clean Architecture (Robert C. Martin)
- Hexagonal Architecture / Ports & Adapters
- Dependency Inversion Principle

### 类似项目参考
- **Claude Code**: 内部工具直接实现，MCP仅用于外部扩展
- **Cursor**: 内置工具函数，MCP为可选协议
- **Continue.dev**: 直接工具调用，MCP作为扩展机制

### 相关文档
- `.claude/todos/architecture-improvements-2026-01-20.md` (优先级1.2: PFC工具重构)
- `.claude/todos/progress-update-2026-01-24.md` (当前架构状态)
- `CLAUDE.md` (项目架构说明)

---

## 🚀 下一步行动

**立即开始（今天）**:
1. 创建 `application/tools/` 目录结构
2. 实现 `base.py` 和 `registry.py`
3. 迁移1个简单工具（read）作为POC
4. 验证架构可行性

**本周完成**:
- Phase 1全部任务
- 至少迁移3个核心工具（read, bash, pfc_execute_task）

**两周内完成**:
- Phase 1 + Phase 2
- 所有工具迁移完成

**三周内完成**:
- 全部三个Phase
- MCP Server默认不再启动（保留可选外部接入）
- 文档更新完整

---

**Document Version**: 1.0
**Last Updated**: 2026-01-25
**Owner**: Architecture Team
**Reviewers**: Core Contributors
