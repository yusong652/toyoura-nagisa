# MCP 架构规划：Client 优先 + pfc-mcp 独立化

**Created**: 2026-01-29
**Status**: Planning
**Priority**: P1
**Impact**: 架构解耦 + 生态扩展

---

## 背景讨论

### 当前状态

- 内部工具已完成 FastMCP 解耦，迁移到 `application/tools/`
- `infrastructure/mcp/mcp_server.py` 目前是空壳（预留对外暴露）
- pfc_* 工具在 `application/tools/pfc/` 直接调用 WebSocket

### 核心问题

1. **作为 MCP 消费者**：toyoura-nagisa 需要连接外部 MCP 服务（context7, blender-mcp 等）
2. **作为 MCP 提供者**：未来需要将 PFC 能力暴露给其他 AI 工具

---

## 架构决策

### 决策 1: 消费者不需要 FastMCP

| 角色 | 需要什么 |
|------|---------|
| MCP Server 提供者 | FastMCP 或 `mcp` SDK |
| MCP Client 消费者 | 只需 `mcp` SDK 的 Client |

**结论**：toyoura-nagisa 作为消费者，只需实现 MCP Client，不需要 FastMCP。

### 决策 2: pfc-mcp 应该完全独立

**反对方案 C（代码复用）**：
```
❌ pfc-mcp → import → toyoura-nagisa/backend/application/tools/pfc/
```
这会破坏解耦，违背 MCP 设计哲学。

**采用方案 B（完全独立）**：
- pfc-mcp 作为独立项目/仓库
- PFC 用户可以直接贡献，不需要理解 toyoura-nagisa
- 任何 MCP Client 都能使用（Claude Code, Cursor, etc.）

---

## 目标架构

### 整体视图

```
┌─────────────────────────────────────────────────────────────┐
│  toyoura-nagisa                                             │
│  职责：AI Agent 平台、对话编排、通用工具                      │
│  内置：read, write, bash, grep, edit, glob (通用工具)       │
│  外部：通过 MCP Client 按需加载领域工具                      │
└─────────────────────────────────────────────────────────────┘
                              ↓ MCP Client
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   pfc-mcp     │    │ context7-mcp  │    │ blender-mcp   │
│  (独立项目)    │    │ (社区项目)     │    │ (社区项目)     │
└───────┬───────┘    └───────────────┘    └───────────────┘
        ↓ WebSocket
┌───────────────┐
│  pfc-server   │
│  (PFC 内部)    │
└───────────────┘
```

### pfc-mcp 与 blender-mcp 对比

两者架构完全一致：

| 方面 | blender-mcp | pfc-mcp (规划) |
|------|-------------|----------------|
| 宿主软件 | Blender | ITASCA PFC |
| 内部服务 | addon.py (Socket) | pfc-server (WebSocket) |
| 外部 MCP | blender-mcp server | pfc-mcp server |
| 端口 | 9876 | 9001 |
| Python 受限 | Blender Python | PFC Python |

### pfc-mcp 项目结构（独立）

```
pfc-mcp/                        # 独立仓库
├── src/pfc_mcp/
│   ├── server.py               # FastMCP Server
│   ├── connection.py           # WebSocket Client → pfc-server
│   ├── tools/
│   │   ├── execute_task.py     # pfc_execute_task
│   │   ├── query_command.py    # pfc_query_command
│   │   ├── query_python_api.py # pfc_query_python_api
│   │   ├── check_status.py     # pfc_check_task_status
│   │   ├── list_tasks.py       # pfc_list_tasks
│   │   └── capture_plot.py     # pfc_capture_plot
│   └── resources/
│       └── pfc_docs/           # PFC 文档资源（可选）
├── pyproject.toml
├── README.md                   # "AI-powered PFC control via MCP"
└── LICENSE
```

### toyoura-nagisa MCP Client

```
packages/backend/
├── infrastructure/
│   └── mcp/
│       ├── client.py           # 通用 MCP Client
│       ├── server_manager.py   # 管理外部 MCP 服务器进程
│       └── tool_adapter.py     # 将 MCP 工具适配为内部 ToolSchema
└── config/
    └── mcp_servers.yaml        # 外部 MCP 服务器配置
```

配置示例：
```yaml
mcp_servers:
  - name: context7
    command: uvx
    args: ["context7-mcp"]
    enabled: true

  - name: pfc-mcp
    command: uvx
    args: ["pfc-mcp"]
    enabled: true
    requires: pfc-server  # 依赖 pfc-server 运行

  - name: blender-mcp
    command: uvx
    args: ["blender-mcp"]
    enabled: false
```

---

## 实施路径

### Phase 1: MCP Client 实现

**目标**：让 toyoura-nagisa 能连接外部 MCP 服务

**任务**：
- [ ] 1.1 实现 `infrastructure/mcp/client.py` (基于 mcp SDK)
- [ ] 1.2 实现 `infrastructure/mcp/server_manager.py` (进程管理)
- [ ] 1.3 实现 MCP 工具到内部 ToolSchema 的适配
- [ ] 1.4 验证：连接 context7-mcp，测试 `resolve-library-id` 和 `query-docs`
- [ ] 1.5 配置化：`mcp_servers.yaml` 支持动态加载

**验收标准**：
- 能通过 MCP Client 调用 context7 工具
- 工具列表动态加载，无需硬编码

### Phase 2: pfc-mcp 独立项目

**目标**：将 PFC 能力暴露为独立 MCP 服务

**任务**：
- [ ] 2.1 创建独立仓库 `pfc-mcp`
- [ ] 2.2 实现 WebSocket Client（连接 pfc-server）
- [ ] 2.3 实现核心工具：
  - [ ] `pfc_execute_task`
  - [ ] `pfc_check_task_status`
  - [ ] `pfc_list_tasks`
  - [ ] `pfc_query_command`
  - [ ] `pfc_query_python_api`
- [ ] 2.4 发布到 PyPI（支持 `uvx pfc-mcp`）
- [ ] 2.5 文档：让其他 AI 工具用户能快速上手

**验收标准**：
- `uvx pfc-mcp` 能启动 MCP 服务器
- Claude Code / Cursor 能通过 MCP 控制 PFC

### Phase 3: toyoura-nagisa 迁移

**目标**：toyoura-nagisa 通过 MCP Client 使用 pfc-mcp

**任务**：
- [ ] 3.1 移除 `application/tools/pfc/`（或保留为 fallback）
- [ ] 3.2 配置 pfc-mcp 为默认 PFC 工具来源
- [ ] 3.3 更新文档

**可选**：保留内部 pfc 工具作为无 MCP 模式的 fallback

---

## 优势总结

### 对 toyoura-nagisa

- **更纯粹**：专注于 AI Agent 平台，不包含领域特定实现
- **更灵活**：通过 MCP 热插拔任何外部服务
- **更简洁**：减少代码量，降低维护成本

### 对 pfc-mcp

- **独立项目**：PFC 用户可以直接贡献
- **通用性**：任何 MCP Client 都能使用
- **专注**：只关注 PFC，不分散注意力

### 对生态

- **标准化**：遵循 MCP 协议，与社区一致
- **可组合**：pfc-mcp + blender-mcp + context7 自由组合
- **开放**：其他 AI 工具可以直接使用 pfc-mcp

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| MCP Client 实现复杂度 | 中 | 参考 mcp SDK 官方示例 |
| pfc-mcp 维护成本 | 中 | 作为独立项目，吸引 PFC 社区贡献 |
| 迁移期间功能中断 | 低 | 保留内部 pfc 工具作为 fallback |

---

## 参考

### 类似架构

- **blender-mcp**: 独立项目，MCP Server + Socket Client
- **context7-mcp**: 独立项目，文档查询服务
- **Claude Code**: MCP Client 连接用户配置的外部服务

### 相关文档

- `.claude/todos/p0-fastmcp-decoupling-2026-01-25.md` - FastMCP 解耦计划（已完成内部工具迁移）
- `services/pfc-server/README.md` - pfc-server 实现细节

---

## 下一步行动

**立即开始**：
1. 调研 `mcp` SDK 的 Client 实现
2. 实现最小可行的 MCP Client
3. 验证能连接 context7-mcp

**本周目标**：
- Phase 1 完成
- context7 集成可用

---

**Document Version**: 1.0
**Last Updated**: 2026-01-29
**Owner**: Architecture Team
