# PFC-MCP 外部项目提取方案

**Created**: 2026-02-07
**Status**: Phase 1 Complete / Phase 2 In Progress (Core Complete, Integration Pending)
**Branch**: `feature/pfc-mcp-extraction-plan`
**Prerequisite**: P0 FastMCP 解耦已完成（内部工具已直接调用，MCP 仅用于外部工具接入）

---

## 目标

将 toyoura-nagisa 中的 PFC 相关能力（工具、文档基础设施、WebSocket 服务）提取为独立的 `pfc-mcp` 项目，通过 MCP 协议对外提供 PFC 仿真控制服务。

**核心价值**:
- **关注点分离**: toyoura-nagisa 专注 AI Agent 平台，pfc-mcp 专注 PFC 仿真控制
- **面向人群拓展**: pfc-mcp 可被任何 MCP 客户端（Claude Desktop、Cursor、其他 AI Agent）使用
- **独立迭代**: PFC 工具、文档、服务器可独立版本管理和发布

---

## 讨论要点分析

### 1. 复杂参数处理：MCP Client 兼容性分析

#### 当前参数复杂度概况

| 工具 | 参数复杂度 | 关键类型 |
|------|-----------|----------|
| `pfc_execute_task` | 中等 | `ScriptPath`, `TaskDescription`, `TimeoutMs`, `RunInBackground` — 全部是标量 + Annotated 校验 |
| `pfc_check_task_status` | 低 | `TaskId`, `SkipNewestLines`, `OutputLimit`, `FilterText`, `WaitSeconds` — 全部标量 |
| `pfc_list_tasks` | 低 | `session_id`, `SkipNewestTasks`, `TaskListLimit` — 全部标量 |
| `pfc_interrupt_task` | 低 | `TaskId` — 单一标量 |
| `pfc_capture_plot` | **高** | 嵌套 `CutPlane(BaseModel)`, `Literal` 枚举, `List[float, 3]`, `ValidatedBallColorBy` (Union + BeforeValidator) |
| `pfc_query_command` | 低 | `SearchQuery`, `SearchLimit` — 标量 |
| `pfc_query_python_api` | 低 | 同上 |
| `pfc_browse_commands` | 低 | `Optional[str]` |
| `pfc_browse_python_api` | 低 | `Optional[str]` |
| `pfc_browse_reference` | 低 | `Optional[str]` |

#### 结论：**MCP 协议完全能处理所有参数复杂度**

**原因**:

1. **MCP 工具参数 = JSON Schema**：MCP 协议中 tool 的 `inputSchema` 就是标准 JSON Schema，支持：
   - `object` 嵌套（CutPlane → `{"type": "object", "properties": {"origin": ..., "normal": ...}}`）
   - `enum`/`const`（Literal → `{"enum": ["sphere", "arrow"]}`）
   - `array` 约束（`List[float, 3]` → `{"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}`）
   - `anyOf`/`oneOf`（Union types → `{"anyOf": [...]}`）
   - `nullable`（Optional → `{"type": ["string", "null"]}` 或 `{"nullable": true}`）

2. **FastMCP 原生支持 Pydantic**：FastMCP `@mcp.tool` 装饰器直接从 Python 类型标注生成 JSON Schema：
   ```python
   @mcp.tool
   def pfc_capture_plot(
       output_path: Annotated[str, Field(description="...")],
       size: Annotated[List[int], Field(min_length=2, max_length=2)] = [720, 480],
       ball_cut: Optional[CutPlane] = None,  # Pydantic BaseModel → nested object schema
   ) -> dict: ...
   ```
   FastMCP 会自动将 `CutPlane(BaseModel)` 内联为 JSON Schema object，无需手动处理。

3. **我们的 MCP Client 已经能处理**：`MCPClient.call_tool()` 接收 `arguments: dict[str, Any]`，直接透传 JSON。`ToolSchema.from_mcp_tool()` 和 `transform_schema_for_openai_compat()` 已实现 `$ref` 内联、`anyOf` → `nullable` 转换。

4. **唯一需要注意**：`ValidatedBallColorBy` 等 `Union[Literal[...], Annotated[str, pattern]]` + `BeforeValidator` 的类型，其 JSON Schema 表达会比较冗长（`anyOf` with multiple items）。MCP Server 端应简化为 `string` + `description` 说明合法值，将 **alias 规范化** 和 **校验** 放在 server 端 Python 代码中而非 JSON Schema 中，这样对 LLM 更友好。

**实现难度**: **低**。10 个工具中 9 个参数都是简单标量，唯一复杂的 `pfc_capture_plot` 也可被 FastMCP + Pydantic 完美处理。

---

### 2. 文档基础设施迁移分析

#### 当前文档系统架构

```
packages/backend/infrastructure/pfc/
├── resources/                     # 静态文档数据（JSON 文件）
│   ├── command_docs/
│   │   ├── index.json             # 命令索引（7 个分类、115+ 命令）
│   │   └── commands/{category}/{command}.json
│   ├── python_api_docs/
│   │   ├── index.json             # Python API 索引
│   │   ├── modules/{module}.json
│   │   ├── functions/{module}/{func}.json
│   │   ├── objects/{object}.json
│   │   └── methods/{object}/{method}.json
│   └── reference_docs/
│       ├── index.json             # 参考文档索引
│       └── {category}/{item}.json
├── commands/
│   ├── loader.py                  # CommandLoader (lru_cache, JSON 加载)
│   └── formatter.py               # CommandFormatter (LLM 可读格式化)
├── python_api/
│   ├── loader.py                  # APILoader
│   └── formatter.py               # APIFormatter
├── references/
│   ├── loader.py                  # ReferenceLoader
│   └── formatter.py               # ReferenceFormatter
└── shared/
    ├── search/
    │   ├── engines/bm25_engine.py # BM25 全文搜索引擎
    │   └── models.py              # SearchResult, Document
    ├── query/
    │   ├── command_search.py      # CommandSearch (facade)
    │   └── api_search.py          # APISearch (facade)
    └── adapters/
        ├── command_adapter.py     # CommandDocumentAdapter (索引构建)
        └── api_adapter.py         # ApiDocumentAdapter
```

#### 迁移难度评估：**中等，但可整体搬移**

**利好因素**:
1. **自包含**: 文档系统几乎完全自包含，唯一的外部依赖是:
   - `@lru_cache` — Python 标准库
   - `Pydantic` — FastMCP 已引入
   - `pathlib` / `json` — 标准库
2. **无 toyoura-nagisa 框架依赖**: Loader/Formatter/Search 不依赖 backend 的 FastAPI、WebSocket 等基础设施
3. **静态资源**: `resources/` 目录可直接 copy，是纯 JSON 数据

**需要处理的点**:
1. **路径解析**: Loader 使用 `Path(__file__).parent` 定位 resources 目录，迁移后需调整相对路径
2. **搜索引擎**: BM25 引擎需要 `pydantic` 和自定义的 `Document`/`SearchResult` 模型，需一并迁移
3. **Formatter 输出格式**: 当前 Formatter 输出是面向 LLM 的 Markdown 文本，可直接作为 MCP tool 返回的 `TextContent`

**迁移策略**: 整体搬移 `infrastructure/pfc/` 到 pfc-mcp 项目，重构 import 路径。这是最简单的方式，因为内部结构已经是模块化的。

---

### 3. pfc-server 合并分析

#### 当前 pfc-server 架构

```
services/pfc-server/           # 独立 WebSocket 服务，运行在 PFC GUI 的 Python 环境中
├── server/
│   ├── server.py              # PFCWebSocketServer (WebSocket 入口)
│   ├── execution/
│   │   ├── main_thread.py     # MainThreadExecutor (线程安全队列)
│   │   └── script.py          # ScriptRunner (实时输出捕获)
│   ├── handlers/              # 消息处理器 (execute, check_status, ...)
│   ├── tasks/
│   │   ├── manager.py         # TaskManager (任务生命周期)
│   │   └── persistence.py     # JSON 持久化
│   ├── signals/
│   │   ├── interrupt.py       # 中断信号处理
│   │   └── diagnostic.py      # 诊断信号处理
│   └── services/
│       └── user_console.py    # 用户控制台
└── start_server.py            # PFC GUI 启动入口
```

**关键约束**:
- pfc-server **必须** 运行在 PFC GUI 的 Python 环境中（使用 `itasca` SDK）
- 依赖 `websockets==9.1`（PFC 嵌入 Python 环境限制）
- 通过 `exec(open(...).read())` 在 PFC GUI IPython 控制台中启动

#### 结论：**不应合并到 pfc-mcp 进程中，但应归属 pfc-mcp 项目**

**架构**:
```
pfc-mcp (项目仓库)
├── pfc-mcp-server/          # MCP Server (FastMCP, 标准 Python 环境)
│   ├── tools/               # MCP 工具定义
│   ├── docs/                # 文档基础设施
│   └── client/              # WebSocket Client → 连接 pfc-bridge
├── pfc-bridge/              # Bridge Server (PFC GUI Python 环境, websockets==9.1)
│   ├── server/              # 当前 pfc-server 代码重命名
│   └── start_bridge.py      # PFC GUI 启动入口
└── README.md
```

**为什么不合并进程**:
1. **Python 环境不同**: pfc-bridge 必须在 PFC GUI 嵌入 Python (3.8+, websockets==9.1) 中运行；pfc-mcp-server 运行在标准 Python 环境
2. **运行位置不同**: pfc-bridge 在 PFC 工作站上运行（可能是 Windows + PFC GUI）；pfc-mcp-server 可在任何位置运行
3. **线程安全**: PFC SDK 要求主线程执行，这个约束只存在于 pfc-bridge 进程

**为什么应归属同一项目**:
1. **单一职责**: pfc-mcp 项目 = "通过 MCP 控制 PFC"，包含完整工具链
2. **版本协同**: bridge 协议变更和 MCP tool 变更需要协同版本管理
3. **部署文档**: 安装说明在一个地方（先装 bridge，再启动 MCP server）
4. **简化 toyoura-nagisa**: 移除 `services/pfc-server/` 后，toyoura-nagisa 完全不含 PFC 特定代码

---

## 项目架构设计

### pfc-mcp 目录结构

```
pfc-mcp/
├── pyproject.toml                  # FastMCP + websockets + pydantic
├── README.md                       # 安装、配置、使用说明
│
├── src/
│   └── pfc_mcp/
│       ├── __init__.py
│       ├── server.py               # FastMCP 服务器入口
│       │
│       ├── tools/                  # MCP 工具定义
│       │   ├── __init__.py
│       │   ├── execute_task.py     # pfc_execute_task
│       │   ├── execute_code.py     # pfc_execute_code (User Console)
│       │   ├── check_task_status.py
│       │   ├── list_tasks.py
│       │   ├── interrupt_task.py
│       │   ├── capture_plot.py     # pfc_capture_plot
│       │   ├── query_command.py    # pfc_query_command
│       │   ├── query_python_api.py
│       │   ├── browse_commands.py
│       │   ├── browse_python_api.py
│       │   └── browse_reference.py
│       │
│       ├── docs/                   # 文档基础设施 (从 infrastructure/pfc/ 迁移)
│       │   ├── resources/          # 静态 JSON 文档数据
│       │   │   ├── command_docs/
│       │   │   ├── python_api_docs/
│       │   │   └── reference_docs/
│       │   ├── commands/           # Loader + Formatter
│       │   ├── python_api/
│       │   ├── references/
│       │   └── search/             # BM25 搜索引擎
│       │       ├── engine.py
│       │       ├── models.py
│       │       ├── command_search.py
│       │       └── api_search.py
│       │
│       ├── bridge/                 # PFC Bridge 通信客户端
│       │   ├── __init__.py
│       │   ├── client.py           # WebSocket Client (连接 pfc-bridge)
│       │   └── task_manager.py     # 任务生命周期管理 (MCP Server 端)
│       │
│       ├── scripts/                # PFC 脚本生成 (capture_plot 等)
│       │   ├── __init__.py
│       │   └── plot_capture.py     # 脚本模板和生成逻辑
│       │
│       └── config.py               # 配置 (bridge URL, 超时等)
│
├── pfc-bridge/                     # PFC GUI Bridge (独立环境)
│   ├── server/                     # 当前 services/pfc-server/server/ 内容
│   │   ├── server.py
│   │   ├── execution/
│   │   ├── handlers/
│   │   ├── tasks/
│   │   ├── signals/
│   │   └── services/
│   ├── start_bridge.py             # PFC GUI 启动入口
│   └── requirements.txt            # websockets==9.1 (不用 pyproject.toml)
│
└── tests/
    ├── test_tools/
    ├── test_docs/
    └── test_bridge_client/
```

### 通信架构

```
MCP Client (Claude Desktop / Cursor / toyoura-nagisa)
    │
    │ MCP Protocol (stdio / SSE)
    ▼
pfc-mcp-server (FastMCP)
    │
    │ Internal: 文档查询 (直接读 JSON，不需要网络)
    │
    │ WebSocket (ws://localhost:9001)
    ▼
pfc-bridge (PFC GUI 内)
    │
    │ itasca SDK (主线程执行)
    ▼
PFC Engine
```

### 工具到 FastMCP 的映射

```python
# src/pfc_mcp/server.py
from fastmcp import FastMCP
from pfc_mcp.tools import (
    execute_task, check_task_status, list_tasks, interrupt_task,
    capture_plot, query_command, query_python_api,
    browse_commands, browse_python_api, browse_reference,
)

mcp = FastMCP(
    "PFC MCP Server",
    instructions="ITASCA PFC discrete element simulation control via MCP protocol.",
)

# 注册所有工具
execute_task.register(mcp)
check_task_status.register(mcp)
# ... etc

if __name__ == "__main__":
    mcp.run()
```

```python
# src/pfc_mcp/tools/execute_task.py
from typing import Annotated, Optional
from pydantic import Field
from fastmcp import FastMCP

def register(mcp: FastMCP):
    @mcp.tool
    async def pfc_execute_task(
        entry_script: Annotated[str, Field(description="Absolute path to PFC Python script")],
        description: Annotated[str, Field(max_length=200, description="Brief task description")],
        timeout: Annotated[Optional[int], Field(ge=1000, le=600000, description="Timeout in ms")] = None,
        run_in_background: Annotated[bool, Field(description="Return immediately with task_id")] = True,
    ) -> str:
        """Execute a PFC simulation task with git version tracking."""
        from pfc_mcp.bridge.client import get_bridge_client
        from pfc_mcp.bridge.task_manager import get_task_manager

        client = await get_bridge_client()
        task_manager = get_task_manager()
        # ... 逻辑与当前 pfc_execute_task 类似，但去除 toyoura-nagisa 特有的:
        #   - ToolContext (无 session_id 概念，MCP server 无状态)
        #   - PfcForegroundExecutionHandle (ctrl+b 是 toyoura-nagisa 前端特性)
        #   - notification_service (前端推送是 toyoura-nagisa 特性)
        ...
```

---

### 4. User Console (`>` 前缀) 归属分析

#### 当前 User Console 完整链路

```
User types "> ball.count()" in CLI/Web
    ↓
Frontend → REST POST /api/pfc/console/execute
    ↓
Backend: pfc_console.py (REST API)
    ├── PfcTaskManager.create_task(source="user_console")
    ├── PFCWebSocketClient.send_user_console(code, workspace_path, task_id)
    ├── StatusMonitor.add_user_pfc_python_context()
    └── 返回 ExecuteData (含 LLM context with caveat)
    ↓
pfc-server: handle_user_console()
    ├── UserConsoleManager.create_script()  → workspace/.user_console/console_001.py
    └── ScriptRunner.run()                  → PFC SDK 主线程执行
    ↓
Result → LLM context injection (XML format + "DO NOT respond" caveat)

CLI 还有 Ctrl+B 支持:
    PfcConsoleService.execute_foreground()
    ├── asyncio.wait([websocket_task, ctrl_b_signal])
    └── PfcConsoleMoveToBackgroundRequest → start_polling
```

#### 涉及的组件

| 组件 | 位置 | 职责 |
|------|------|------|
| REST API | `presentation/api/pfc_console.py` | Web 前端入口，5 个端点 |
| Console Service | `application/pfc/pfc_console_service.py` | CLI 前端入口，Ctrl+B 支持 |
| WebSocket Client | `infrastructure/pfc/client.py` → `send_user_console()` | 通信层 |
| Console Handler | `pfc-server/handlers/console_handlers.py` | 消息处理 |
| UserConsoleManager | `pfc-server/services/user_console.py` | 脚本创建/管理 |
| ScriptRunner | `pfc-server/execution/script.py` | 脚本执行 |

#### 问题：如果不迁移，toyoura-nagisa 仍直连 pfc-bridge

如果 User Console 不走 pfc-mcp，toyoura-nagisa 需要同时维护两条通信通道：
- MCP 协议 → pfc-mcp（10 个 AI 工具）
- WebSocket 直连 → pfc-bridge（User Console）

这意味着 `infrastructure/pfc/client.py` 无法删除，解耦不彻底。

#### 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: Console 走 pfc-mcp** | pfc-mcp 新增 `pfc_execute_code` 工具 | 完全解耦，单通道 | MCP 协议非实时，对 console 交互体验有延迟 |
| **B: 保留直连** | Console 直连 pfc-bridge，工具走 MCP | Console 体验不变 | 不彻底解耦，双通道维护 |
| **C: pfc-mcp 暴露 RPC 端点** | pfc-mcp 除 MCP 外还提供 HTTP/WS API | 灵活 | pfc-mcp 职责膨胀 |

#### 推荐：**方案 A — User Console 走 pfc-mcp**

**理由**:

1. **彻底解耦**: toyoura-nagisa 与 pfc-bridge 零直连，所有 PFC 通信通过 MCP
2. **实现简单**: pfc-mcp 新增一个 `pfc_execute_code` 工具即可
   ```python
   @mcp.tool
   async def pfc_execute_code(
       code: Annotated[str, Field(description="Python code to execute in PFC environment")],
       timeout_ms: Annotated[int, Field(ge=1000, le=60000)] = 30000,
   ) -> str:
       """Execute Python code in PFC Python environment (for interactive console use)."""
       client = await get_bridge_client()
       result = await client.send_user_console(code=code, timeout_ms=timeout_ms)
       return format_result(result)  # TextContent
   ```
3. **toyoura-nagisa 侧改动小**: `pfc_console.py` REST API 改为调用 `MCPClient.call_tool("pfc_execute_code", {...})`
4. **通用性**: 其他 MCP 客户端（Claude Desktop 等）也能获得 console 能力

**需要注意的点**:

1. **延迟**: MCP stdio 通信有少量序列化开销（~几 ms），对 console 场景可接受
2. **Ctrl+B**: 这是 toyoura-nagisa 前端特性，不属于 pfc-mcp 职责
   - **处理方式**: toyoura-nagisa 发起 MCP 调用后，如用户按 Ctrl+B，toyoura-nagisa 取消 MCP 调用（取消等待响应），然后通过 MCP 调用 `pfc_check_task_status` 轮询
   - 或者 `pfc_execute_code` 默认异步 (返回 task_id)，toyoura-nagisa 自己 poll
3. **Script 管理**: UserConsoleManager 迁移到 pfc-bridge（已在 Phase 2 迁移），console 脚本继续存在 PFC workspace 中
4. **LLM Context Caveat**: 这是 toyoura-nagisa 展示层逻辑，保留在 `pfc_console.py` REST API 中
5. **StatusMonitor**: 保留在 toyoura-nagisa，从 MCP 结果中提取数据注入

**改造后的 Console 链路**:
```
User types "> ball.count()"
    ↓
Frontend → REST POST /api/pfc/console/execute
    ↓
Backend: pfc_console.py
    ├── MCPClient.call_tool("pfc_execute_code", {code, timeout_ms})
    │       ↓ MCP stdio
    │   pfc-mcp-server
    │       ├── BridgeClient.send_user_console(code)
    │       │       ↓ WebSocket
    │       │   pfc-bridge: handle_user_console → ScriptRunner
    │       │       ↓
    │       └── return TextContent(result)
    │       ↓ MCP stdio
    ├── StatusMonitor.add_user_pfc_python_context()
    └── 返回 ExecuteData (含 LLM context with caveat)
```

---

## 迁移路径

### Phase 0: 前置准备 (在 toyoura-nagisa 中) — DONE

- [x] 0.1 确认 P0 FastMCP 解耦已完成（内部工具直接调用，MCP Client 接入外部工具）
- [x] 0.2 确认当前所有 PFC 工具测试通过
- [x] 0.3 创建 `pfc-mcp` 子项目（UV workspace member，后续提取为独立仓库）

### Phase 1: 文档系统迁移 — DONE (2026-02-07)

**目标**: 将文档基础设施迁移到 pfc-mcp，实现 browse/query 工具

- [x] 1.1 搬移 `resources/` 静态 JSON 数据 (command_docs, python_sdk_docs, references)
- [x] 1.2 搬移 Loader 层 (`commands/loader.py`, `python_api/loader.py`, `references/loader.py`)
- [x] 1.3 搬移 Formatter 层 (返回 plain str，FastMCP 自动包装为 TextContent)
- [x] 1.4 搬移 Search 层 (BM25 引擎、DocumentAdapter、preprocessing、postprocessing、scoring)
- [x] 1.5 实现 5 个文档工具:
  - `pfc_browse_commands` — 层级浏览命令文档
  - `pfc_browse_python_api` — 层级浏览 Python SDK 文档
  - `pfc_browse_reference` — 层级浏览参考文档 (contact-models, range-elements)
  - `pfc_query_command` — BM25 关键词搜索命令
  - `pfc_query_python_api` — BM25 关键词搜索 Python API
- [ ] 1.6 单元测试: 确认文档查询、搜索、格式化正确

**验收**: ~~`fastmcp dev` 启动后，5 个文档工具可用，Inspector 中能查询到 PFC 命令~~

已验收 (2026-02-07):
- `uv sync --all-packages` 成功，pfc-mcp 作为 workspace member 正确安装
- `from pfc_mcp.server import mcp` → Server name: PFC MCP Server
- 5 个工具全部注册: `pfc_browse_commands`, `pfc_browse_python_api`, `pfc_browse_reference`, `pfc_query_command`, `pfc_query_python_api`
- CommandLoader: 8 categories, 128 commands — OK
- APILoader: 10 modules, 9 objects — OK
- ReferenceLoader: 2 categories (contact-models, range-elements) — OK
- BM25 search: "ball create" → 3 results, "ball position" → 3 results — OK
- 无 toyoura-nagisa 依赖: 所有 `backend.*` import 已替换为 `pfc_mcp.docs.*`

**实际目录结构**:
```
pfc-mcp/
├── pyproject.toml
├── src/pfc_mcp/
│   ├── __init__.py
│   ├── server.py                   # FastMCP entry point
│   ├── utils.py                    # SearchQuery, SearchLimit, normalize_input
│   ├── tools/
│   │   ├── browse_commands.py
│   │   ├── browse_python_api.py
│   │   ├── browse_reference.py
│   │   ├── query_command.py
│   │   └── query_python_api.py
│   └── docs/
│       ├── config.py               # Path(__file__).parent / "resources"
│       ├── resources/              # 静态 JSON (verbatim copy)
│       │   ├── command_docs/
│       │   ├── python_sdk_docs/
│       │   └── references/
│       ├── commands/               # Loader + Formatter + models
│       ├── python_api/             # Loader + Formatter + models + types/
│       ├── references/             # Loader + Formatter
│       ├── models/                 # SearchDocument, SearchResult (from shared/models/)
│       ├── search/                 # BM25 engine (from shared/search/)
│       │   ├── engines/
│       │   ├── indexing/
│       │   ├── preprocessing/
│       │   ├── postprocessing/
│       │   └── scoring/
│       ├── query/                  # CommandSearch, APISearch (from shared/query/)
│       └── adapters/               # Document adapters (from shared/adapters/)
└── tests/
```

**Import 映射** (Phase 1 中实际执行的):
| Original | New |
|---|---|
| `backend.infrastructure.pfc.config` | `pfc_mcp.docs.config` |
| `backend.infrastructure.pfc.commands.*` | `pfc_mcp.docs.commands.*` |
| `backend.infrastructure.pfc.python_api.*` | `pfc_mcp.docs.python_api.*` |
| `backend.infrastructure.pfc.references.*` | `pfc_mcp.docs.references.*` |
| `backend.infrastructure.pfc.shared.models.*` | `pfc_mcp.docs.models.*` |
| `backend.infrastructure.pfc.shared.search.*` | `pfc_mcp.docs.search.*` |
| `backend.infrastructure.pfc.shared.query.*` | `pfc_mcp.docs.query.*` |
| `backend.infrastructure.pfc.shared.adapters.*` | `pfc_mcp.docs.adapters.*` |

**Key design choices**:
- 工具函数返回 `str` (非 Dict envelope)，无 `success_response()`/`error_response()` 包装
- 无 `ToolRegistrar`/`ToolContext`/`session_id` 依赖
- `register(mcp: FastMCP)` 模式，`@mcp.tool()` 装饰器
- `docs/config.py` 使用 `Path(__file__).parent / "resources"` 而非原始的多级 parent 回溯

### Phase 2: Bridge Client + 执行工具 (1 周)

**目标**: 实现 bridge 通信和任务执行工具

- [x] 2.1 搬移 pfc-bridge 代码 (从 `services/pfc-server/`)
- [x] 2.2 重命名和调整 import 路径
- [x] 2.3 实现 `bridge/client.py` — WebSocket Client (基于现有 `infrastructure/pfc/client.py`，去除 toyoura-nagisa 依赖)
- [x] 2.4 实现 `bridge/task_manager.py` — 简化版任务管理器 (去除 foreground handle、notification service)
- [x] 2.5 实现 5 个执行工具:
  - `pfc_execute_task` — 简化: 仅 background 模式 (MCP 是无状态的，没有 foreground/ctrl+b 概念)
  - `pfc_execute_code` — User Console 支持: 接收 Python 代码字符串，交由 bridge 执行
  - `pfc_check_task_status`
  - `pfc_list_tasks` — 返回中包含 `checked` 字段
  - `pfc_interrupt_task`
- [ ] 2.6 集成测试: 连接实际 PFC Bridge 执行任务和 console 代码

已完成 (2026-02-08):
- `pfc-mcp/src/pfc_mcp/bridge/client.py`：新增无 toyoura-nagisa 依赖的 WebSocket bridge client（重连、请求响应、重试）
- `pfc-mcp/src/pfc_mcp/bridge/task_manager.py`：新增 MCP 侧简化任务管理器（6-char task_id）
- 执行工具已注册到 `pfc_mcp.server`：`pfc_execute_task`、`pfc_execute_code`、`pfc_check_task_status`、`pfc_list_tasks`、`pfc_interrupt_task`
- `pfc-mcp/pfc-bridge/` 已引入 bridge runtime 代码（`server/`、`start_bridge.py`、`workspace_template/`、`config_example.py`、`requirements.txt`）
- smoke 验证通过：`from pfc_mcp.server import mcp` + 工具注册列表包含 10 个工具（5 docs + 5 execution）
- `pfc-mcp/tests/test_phase2_tools.py`：新增 Phase 2 单测（工具注册、状态映射、路径校验）
- `uv run pytest pfc-mcp/tests/test_phase2_tools.py --no-cov`：3 passed（仓库全局 coverage gate 不适用于该局部测试）
- `uv run python -m compileall pfc-mcp/src/pfc_mcp pfc-mcp/pfc-bridge`：语法检查通过

进行中:
- 2.6 集成测试待完成：需真实 PFC GUI + bridge 在线环境（本地 dry-run 已完成）

**验收**: 能通过 MCP 协议执行 PFC 仿真、console 代码、并查询状态

### Phase 3: 诊断工具 + 打磨 (0.5 周)

**目标**: 实现 capture_plot，完善配置和错误处理

- [ ] 3.1 搬移脚本模板 (`scripts/plot_capture_template.py`)
- [ ] 3.2 实现 `pfc_capture_plot` 工具
  - 关键: MCP 支持 `ImageContent`，可直接返回截图 base64
  - 替代当前"返回路径 + 让 LLM 用 read() 加载"的模式
- [ ] 3.3 配置系统: bridge URL、超时、workspace 路径
- [ ] 3.4 错误处理: bridge 断连重试、优雅错误消息
- [ ] 3.5 完善 README

**验收**: 所有 10 个工具可用，配置清晰，错误处理健壮

### Phase 4: toyoura-nagisa 侧清理 (0.5 周)

**目标**: toyoura-nagisa 通过 MCP Client 接入 pfc-mcp

**清理时机约束**:
- 不提前删除 toyoura-nagisa 内部 PFC 代码；待 Phase 3 + Phase 4.1~4.6 验证通过后，再执行 4.7~4.9 的物理删除
- 原则：先切流验证，再删旧链路（避免在 bridge/console 未稳定前丢失回滚路径）

- [ ] 4.1 在 `config/mcp_servers.yaml` 中配置 pfc-mcp server:
  ```yaml
  servers:
    - name: pfc-mcp
      command: uvx
      args: ["pfc-mcp"]  # 或 uv run python -m pfc_mcp
      enabled: true
      description: "PFC simulation control and documentation"
  ```
- [ ] 4.2 验证 MCPClientManager 自动加载 pfc-mcp 工具
- [ ] 4.3 验证 `transform_schema_for_openai_compat()` 处理 pfc_capture_plot 的 schema
- [ ] 4.4 验证 SubAgent (pfc_explorer, pfc_diagnostic) 能使用 pfc-mcp 工具
- [ ] 4.5 改造 User Console:
  - `pfc_console.py` REST API → 改用 `MCPClient.call_tool("pfc_execute_code", {code, timeout_ms})`
  - `pfc_console_service.py` CLI → 同上，Ctrl+B 改为: 取消 MCP 等待 + 切换为 `pfc_check_task_status` 轮询
  - 保留 caveat injection / StatusMonitor 逻辑（这是 toyoura-nagisa 展示层职责）
- [ ] 4.6 改造 Notified → Checked 机制:
  - pfc-bridge: `check_task_status` 隐式标记终态任务 `checked=True` (持久化)
  - pfc-bridge: 移除 `mark_task_notified` handler，`notified` 字段重命名为 `checked`
  - `PfcMonitor.get_reminders()` → `pfc_list_tasks` 看 `checked` 字段 → 未 checked 的完成任务 → 调 `pfc_check_task_status` 获取详情 (副作用: 标记 checked)
  - `PfcTaskNotificationService._polling_loop()` → 改用 MCP 调用 `pfc_check_task_status` 轮询
  - `PfcTaskManager` 内存层保持不变（session-scoped 快速层）
  - 验证: backend 重启后不重复通知（依赖 pfc-bridge 持久化的 `checked` 标记）
- [ ] 4.7 移除 `packages/backend/application/tools/pfc/` (内部 PFC 工具)
- [ ] 4.8 移除 `packages/backend/infrastructure/pfc/` (文档基础设施 + WebSocket Client)
- [ ] 4.9 移除 `services/pfc-server/` (bridge 已在 pfc-mcp 项目中)
- [ ] 4.10 更新 CLAUDE.md、agents.yaml、相关文档

**验收**: toyoura-nagisa 不再包含任何 PFC 特定代码，所有 PFC 功能（含 User Console）通过 MCP 协议获得

---

## 关键设计决策

### D1: MCP Server 无状态 vs 有状态

**决策**: **无状态 MCP Server + Bridge 有状态**

- MCP Server 不维护 session 概念（MCP 协议本身没有 session）
- 任务状态由 Bridge 持久化（JSON 文件在 PFC workspace 中）
- MCP Server 每次调用都通过 bridge client 查询最新状态
- 原有的 `foreground mode` (ctrl+b) 是 toyoura-nagisa 前端特性，在 MCP 版本中不需要
  - pfc-mcp 中 `pfc_execute_task` 默认且只支持 `run_in_background=True`
  - 或者: 保留 `run_in_background` 参数，但 `=False` 时 MCP server 内部 poll 等待完成再返回

### D2: pfc_capture_plot 返回方式

**决策**: **返回 ImageContent（MCP 原生图片支持）**

当前 toyoura-nagisa 版本: 返回文件路径 → LLM 用 `read()` 工具加载图片
pfc-mcp 版本: 直接读取 PNG 文件 → base64 编码 → 返回 `types.ImageContent`

```python
import base64
from mcp.types import ImageContent, TextContent

# 执行截图后
with open(output_path, "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

return [
    ImageContent(type="image", data=image_data, mimeType="image/png"),
    TextContent(type="text", text=f"Plot captured: {output_path}"),
]
```

**好处**: MCP 客户端（如 Claude Desktop）可直接显示图片，无需额外 read 工具

### D3: 文档工具 — Resource vs Tool

**决策**: **保持 Tool 模式，不使用 MCP Resource**

- 虽然 MCP 有 Resource 概念（`mcp://pfc/commands/ball/create`），但当前 LLM 客户端对 Resource 的支持不如 Tool 成熟
- 保持 browse/query 作为 Tool，LLM 可以主动搜索和导航
- 未来可以同时暴露 Resource（让客户端预加载常用文档）

### D4: 参数校验策略

**决策**: **Server 端严格校验 + Schema 从简**

- JSON Schema 中使用简洁描述（避免过长的 enum 列表让 LLM 困惑）
- 例如 `ball_color_by`: Schema 用 `{"type": "string", "description": "Ball coloring attribute. See pfc_browse_commands for valid values."}`
- 实际校验在 Python 代码中（BeforeValidator + alias 规范化）
- 这样 LLM 看到的 schema 更简洁，而 server 端保证数据正确

### D5: Notified → Checked 语义重构

**问题**: 当前 `notified` 机制需要单独的 `mark_task_notified` 调用，提取后如果再暴露为 MCP 工具，既不优雅也违背工具设计原则（工具应对应有意义的用户动作，而非内部记账）。

**当前机制**:

```
PfcMonitor.get_reminders()
  → client.list_tasks()          # 查询，返回 notified 字段
  → 发现 notified=False 的已完成任务
  → 生成 <system-reminder>
  → client.mark_task_notified()  # 额外调用标记 ← 不优雅
```

**核心洞察**: **检查本身就是通知行为**——当有人调用 `pfc_check_task_status` 查看一个已完成任务的结果时，这个 "看过了" 的事实就是 notified 的语义。

**决策**: **将 `notified` 重构为 `checked`，由 `pfc_check_task_status` 隐式标记**

**pfc-bridge 侧改动** (原 pfc-server):

```python
# tasks/manager.py
def check_task_status(self, task_id):
    task = self.tasks.get(task_id)
    if not task:
        return {"status": "not_found"}

    # 核心: 查看终态任务 = 确认已知晓
    if task.is_terminal and not task.checked:
        task.checked = True
        self._save_tasks()        # 持久化，跨重启

    return {"status": task.status, "data": {..., "checked": task.checked}}
```

**pfc-mcp 侧**: 零额外逻辑。`pfc_check_task_status` 透传 bridge 的返回，`pfc_list_tasks` 返回中自带 `checked` 字段。不需要 `pfc_mark_task_notified` 工具。

**toyoura-nagisa 侧 — PfcMonitor 改造**:

```python
async def get_reminders(self, agent_profile="pfc_expert"):
    mcp = get_mcp_client_manager()

    # 1. 查列表，拿到 checked 字段
    list_result = await mcp.call_tool("pfc_list_tasks", {"limit": 3})
    tasks = parse_task_list(list_result)  # 解析 MCP TextContent

    reminders = []
    for task in tasks:
        if task.is_terminal and not task.checked:
            # 2. 调 check_task_status 获取详情 (副作用: 标记 checked=True)
            detail = await mcp.call_tool("pfc_check_task_status", {"task_id": task.task_id})
            reminders.append(format_completion_reminder(task, detail))
        elif task.status == "running":
            reminders.append(format_running_reminder(task))

    return reminders
    # 下次循环: 同一任务 checked=True，不再提醒
```

**效果**:
- 去掉 `mark_task_notified` 工具和 bridge 端的 `handle_mark_task_notified` handler
- 去掉 `PFCWebSocketClient.mark_task_notified()` 方法
- `pfc_check_task_status` 本身就是 "已确认" 的语义锚点
- 对任何 MCP 客户端通用：Claude Desktop 用户调 `pfc_check_task_status` 也会自动标记 checked
- LLM 主动调用 `pfc_check_task_status` 也会标记——与 PfcMonitor 的 reminder 幂等（都标记为 checked，谁先到都行）

**PfcTaskManager (内存层)**: `completion_notified` 保持不变，作为 session-scoped 快速层。与 bridge 持久化的 `checked` 互补——内存层防止同一 session 内重复提醒，持久化层防止 backend 重启后重复提醒。

### D6: User Console 的 Ctrl+B 适配

**决策**: **pfc_execute_code 默认同步（等完成再返回），Ctrl+B 由 toyoura-nagisa 取消 MCP 调用**

- `pfc_execute_code` MCP 工具接受 `timeout_ms` 参数，在 server 端等待执行完成后返回
- 如果 toyoura-nagisa 用户按 Ctrl+B:
  1. toyoura-nagisa 取消当前 MCP 调用的等待（丢弃 pending response）
  2. 脚本在 pfc-bridge 中继续执行（不中断）
  3. toyoura-nagisa 调用 `pfc_check_task_status` 切换为轮询模式
  4. 前端开始显示 task notification
- 这样 Ctrl+B 的实现完全在 toyoura-nagisa 侧，pfc-mcp 无需感知

**替代方案**: `pfc_execute_code` 默认异步（返回 task_id），toyoura-nagisa 自行 poll。但这会让简单的 `> ball.count()` 也需要两次 MCP 调用（execute + check_status），体验更差。

### D7: pfc-bridge 目录位置

**决策**: **`pfc-bridge/` 与 `src/` 并列，不放入 `src/pfc_mcp/`**

- `src/pfc_mcp/` 是可打包发布的 MCP server 包
- `pfc-bridge/` 是 PFC GUI 环境独立运行时（`itasca` + `websockets==9.1`）
- 分离可避免 bridge 运行时依赖污染主包，并保持部署语义清晰（MCP server / bridge 双进程）

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Bridge 通信协议变更不兼容 | 高 | 低 | bridge 保持现有 WebSocket 协议不变，pfc-mcp client 适配 |
| pfc_capture_plot 跨机器文件访问 | 中 | 中 | 当 MCP server 和 Bridge 在同一机器时可直接读文件；远程场景需 bridge 返回 base64 |
| LLM 对复杂 tool schema 理解不准 | 中 | 低 | 简化 schema（D4），提供详细 description |
| SubAgent 通过 MCP 调用延迟增加 | 中 | 中 | SubAgent 高频调用文档工具，考虑本地缓存或保留文档工具内部副本 |
| pfc-bridge 环境限制 (websockets==9.1) | 低 | 已知 | 独立 requirements.txt，不受 pfc-mcp 主项目依赖影响 |
| User Console 延迟增加 (MCP 中转) | 低 | 中 | MCP stdio 序列化仅增加几 ms，console 场景可接受；Ctrl+B 取消等待不阻塞用户 |
| User Console Ctrl+B 改造复杂度 | 中 | 中 | 将 asyncio.wait 改为 MCP 调用取消 + poll 切换，逻辑更简单（去掉 ForegroundHandle） |

---

## 后续扩展

1. **MCP Resource 支持**: 暴露 PFC 文档为 Resource，客户端可预加载
2. **SSE Transport**: 除 stdio 外支持 SSE，方便远程访问
3. **多 Bridge 支持**: 一个 MCP Server 连接多个 PFC 实例
4. **PyPI 发布**: `pip install pfc-mcp`，用户一行命令安装
5. **pfc-bridge 独立包**: `pip install pfc-bridge`，在 PFC GUI 中安装

---

**Document Version**: 1.2
**Last Updated**: 2026-02-08
