# PFC-MCP Phase 5: 正交化与后续解耦

**Created**: 2026-02-08
**Status**: Planning
**Branch**: `feature/pfc-mcp-extraction-plan`
**Prerequisite**: Phase 1-3 代码完成，Phase 4 部分完成（bridge/tools 已物理移除，MCP 接入和 client 清理待完成）

---

## 背景

Phase 1-3 已将 PFC 工具、文档基础设施、bridge runtime 迁移到 `pfc-mcp/` 项目。但当前存在两个正交化问题：

1. **pfc-mcp 包含了不属于它的职责**：git version tracking 是 toyoura-nagisa "script is context" 哲学的产物，不是通用 PFC 仿真控制需要的功能
2. **toyoura-nagisa 仍然直连 pfc-bridge**：User Console、PfcMonitor、NotificationService 仍通过直接 WebSocket 而非 MCP 协议通信

要让 pfc-mcp 被更广泛地采用（Claude Desktop、Cursor 用户），需要：
- pfc-mcp 只提供 PFC 仿真控制的核心能力（执行、监控、文档查询、截图）
- toyoura-nagisa 特有的增强功能（git 快照、前端通知、Ctrl+B 前台模式）留在 toyoura-nagisa 侧

---

## 问题分析

### P1: Git Version Tracking 不应在 pfc-bridge 中

**当前位置**:
- `pfc-mcp/pfc-bridge/server/services/git_version.py` — 441 行的 `GitVersionManager`
- `pfc-mcp/pfc-bridge/server/execution/script.py:320-327` — 执行前创建 git commit
- `pfc-mcp/pfc-bridge/server/handlers/task_handlers.py:52` — `enable_git_snapshot = (source == "agent")`
- `pfc-mcp/pfc-bridge/server/handlers/workspace_handlers.py:96-99` — `reset_execution_branch()`

**问题**:
- Git 快照是 toyoura-nagisa 的 "script is context" 策略，记录每次 agent 执行的代码状态
- 其他 MCP 客户端（Claude Desktop）不需要也不理解这个概念
- pfc-bridge 强依赖 git 命令（`subprocess.run(["git", ...])`)，而 PFC 工作站不一定有 git
- `source == "agent"` 判断泄露了 toyoura-nagisa 的业务语义到 pfc-bridge

**方案分析**:

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 调用方创建快照** | toyoura-nagisa 在调用 `pfc_execute_task` MCP 前自行 git commit | pfc-bridge 零 git 依赖；调用方完全控制 | git 快照和执行不是原子的（中间可能有文件变动） |
| **B: pfc-bridge 可选 flag** | 保留 git 逻辑但默认关闭，`pfc_execute_task` 传 `enable_git_snapshot` 参数 | 最小改动 | pfc-bridge 仍包含 git 代码；维护负担 |
| **C: pfc-bridge 插件/hook** | git 逻辑作为可选 hook 注册到 bridge | 可扩展 | 过度设计 |

**推荐: 方案 A — 调用方创建快照**

**理由**:
1. **单一职责**: pfc-bridge 只负责 PFC SDK 执行，不管版本控制
2. **原子性可接受**: 快照捕获的是"决策时刻的代码状态"，而非"执行瞬间的状态"。在调用 MCP 前 commit 是合理的语义——AI agent 写好脚本 → commit 快照 → 提交执行
3. **简化 pfc-bridge**: 移除 ~500 行 git 代码 + subprocess 依赖
4. **简化协议**: 去掉 `source` 字段在 git 判断中的角色；`git_commit` 返回字段从 bridge 侧消除
5. **Git 快照 → toyoura-nagisa 的 invoke_agent 或 pfc_execute_task 工具包装**: 在内部工具层执行 git 操作

**改造后的链路**:
```
toyoura-nagisa: pfc_execute_task (内部工具)
  1. GitVersionManager.create_execution_commit()  ← 移到 toyoura-nagisa
  2. MCPClient.call_tool("pfc_execute_task", {...})
  3. 返回结果 + git_commit (本地记录)

pfc-bridge: handle_pfc_task()
  - 不再有 enable_git_snapshot 逻辑
  - 不再返回 git_commit
  - 纯粹执行脚本
```

**需要处理的文件**:
- `pfc-mcp/pfc-bridge/server/services/git_version.py` → 移到 `packages/backend/infrastructure/pfc/git_version.py`
- `pfc-mcp/pfc-bridge/server/execution/script.py` → 移除 git 相关 import 和逻辑
- `pfc-mcp/pfc-bridge/server/handlers/task_handlers.py` → 移除 `enable_git_snapshot` 参数
- `pfc-mcp/pfc-bridge/server/handlers/workspace_handlers.py` → 移除 git reset 逻辑
- `pfc-mcp/pfc-bridge/server/tasks/task_types.py` → 移除 `git_commit` 字段
- `pfc-mcp/src/pfc_mcp/tools/execute_task.py` → 移除 git_commit 返回显示

---

### P2: Backend 仍直连 pfc-bridge（Phase 4 未完成项）

**当前直连点**:

| 组件 | 文件 | 用途 |
|------|------|------|
| PFC Console REST API | `presentation/api/pfc_console.py` | 5 处 `get_pfc_client()` |
| PFC Console Service | `application/pfc/pfc_console_service.py` | `client.send_user_console()` |
| PFC Monitor | `infrastructure/monitoring/monitors/pfc_monitor.py` | `client.list_tasks()` + `mark_task_notified()` |
| PFC Notification Service | `application/notifications/pfc_task_notification_service.py` | `client.list_tasks()` + `check_task_status()` |
| PFC Execution Service | `application/pfc/pfc_execution_service.py` | ForegroundRegistry + TaskManager |
| Workspace Utils | `shared/utils/workspace.py` | `client.get_working_directory()` |

**目标**: 所有 PFC 通信通过 MCP Client → pfc-mcp，移除 `infrastructure/pfc/client.py`

---

### P3: Notified → Checked 语义（D5 未实施）

**当前状态**: pfc-bridge 仍有 `handle_mark_task_notified` handler，PfcMonitor 仍调用 `client.mark_task_notified()`

**目标**: 实施 D5 — `pfc_check_task_status` 隐式标记 `checked=True`，移除独立的 `mark_task_notified`

---

## 执行路径

### Step 1: Git Version 提取（pfc-bridge 侧清理）

**目标**: pfc-bridge 不再包含 git 逻辑

- [ ] 1.1 将 `git_version.py` 从 `pfc-bridge/server/services/` 移到 `packages/backend/infrastructure/pfc/`
- [ ] 1.2 pfc-bridge `script.py`: 移除 `enable_git_snapshot` 参数和 git commit 逻辑
- [ ] 1.3 pfc-bridge `task_handlers.py`: 移除 `enable_git_snapshot` 参数传递
- [ ] 1.4 pfc-bridge `task_types.py`: 移除 `git_commit` 字段（或保留但不由 bridge 填充）
- [ ] 1.5 pfc-bridge `workspace_handlers.py`: 移除 git reset 逻辑（或保留但标注 optional）
- [ ] 1.6 pfc-bridge `services/__init__.py`: 移除 `get_git_manager` 导出
- [ ] 1.7 pfc-mcp `execute_task.py`: 移除 git_commit 显示逻辑
- [ ] 1.8 验证: pfc-bridge 不再 import git_version，无 subprocess git 调用

### Step 2: toyoura-nagisa 侧 Git 快照集成

**目标**: toyoura-nagisa 的 pfc_execute_task 工具在调用 MCP 前执行 git 快照

- [ ] 2.1 在 `packages/backend/infrastructure/pfc/` 放置 `git_version.py`（从 bridge 迁移）
- [ ] 2.2 重构为使用 `asyncio.to_thread()` 或保持同步（git 操作很快）
- [ ] 2.3 pfc_execute_task 内部工具: 调用前执行 `create_execution_commit()`
- [ ] 2.4 将 git_commit 记录到 PfcTaskManager 本地（非 bridge 侧）
- [ ] 2.5 前端通知中的 git_commit 从 PfcTaskManager 获取（非 bridge 返回）
- [ ] 2.6 验证: git 快照在 MCP 调用前创建，task 信息包含 git_commit

### Step 3: Backend MCP 迁移 — PfcMonitor

**目标**: PfcMonitor 通过 MCP 获取任务状态

- [ ] 3.1 PfcMonitor.get_reminders(): 改用 `MCPClient.call_tool("pfc_list_tasks", {...})`
- [ ] 3.2 解析 MCP TextContent 返回（pfc_list_tasks 返回 str）
- [ ] 3.3 移除 `mark_task_notified` 调用（改为 D5 checked 语义）
- [ ] 3.4 验证: PfcMonitor 不再 import infrastructure.pfc.client

### Step 4: Backend MCP 迁移 — NotificationService

**目标**: PfcTaskNotificationService 通过 MCP 轮询任务状态

- [ ] 4.1 `_polling_loop()`: 改用 MCPClient 调用 `pfc_list_tasks` 和 `pfc_check_task_status`
- [ ] 4.2 `_process_running_task()`: 同上
- [ ] 4.3 `_handle_task_completion()`: 同上
- [ ] 4.4 `notify_foreground_backgrounded()`: 改用 MCP
- [ ] 4.5 验证: NotificationService 不再 import infrastructure.pfc.client

### Step 5: Backend MCP 迁移 — User Console

**目标**: User Console 通过 MCP 执行代码

- [ ] 5.1 pfc-mcp 注册 `pfc_execute_code` 工具（当前实现已有，但未注册）
- [ ] 5.2 `pfc_console_service.py`: 改用 `MCPClient.call_tool("pfc_execute_code", {...})`
- [ ] 5.3 Ctrl+B 改造:
  - 取消 MCP 调用等待（取消 pending response）
  - 脚本在 bridge 继续执行
  - 切换为 `pfc_check_task_status` 轮询模式
- [ ] 5.4 `pfc_console.py` REST API: 改用 MCPClient
- [ ] 5.5 移除 ForegroundHandle 对 WebSocket client 的直接依赖
- [ ] 5.6 验证: Console 链路完全通过 MCP

### Step 6: Notified → Checked 语义实施

**目标**: 实施 D5 决策

- [ ] 6.1 pfc-bridge `task_types.py`: `notified` 字段重命名为 `checked`
- [ ] 6.2 pfc-bridge `manager.py` `get_task_status()`: 终态任务被查询时自动标记 `checked=True`
- [ ] 6.3 pfc-bridge: 移除 `handle_mark_task_notified` handler
- [ ] 6.4 pfc-bridge `server.py`: 移除 `mark_task_notified` 消息路由
- [ ] 6.5 pfc-mcp bridge client: 移除 `mark_task_notified()` 方法（如果有）
- [ ] 6.6 验证: `pfc_list_tasks` 返回 `checked` 字段，`pfc_check_task_status` 自动标记

### Step 7: 清理 infrastructure/pfc

**目标**: 移除不再需要的 WebSocket client 和相关模块

- [ ] 7.1 移除 `infrastructure/pfc/client.py`（~1015 行 WebSocket client）
- [ ] 7.2 移除 `infrastructure/pfc/foreground_handle.py`（已无直连 WebSocket）
- [ ] 7.3 移除 `infrastructure/pfc/foreground_registry.py`（改为本地 asyncio.Event 模式）
- [ ] 7.4 评估 `infrastructure/pfc/task_manager.py` — 保留作为 session-scoped 快速层
- [ ] 7.5 移除 `infrastructure/pfc/__init__.py` 中的 client 导出
- [ ] 7.6 验证: 无任何 `from backend.infrastructure.pfc.client import` 残留

### Step 8: Workspace 路径检测

- [ ] 8.1 `shared/utils/workspace.py`: 改用 MCP 调用 `get_working_directory` 或配置文件
- [ ] 8.2 验证: workspace.py 不再 import pfc client

---

## 依赖关系

```
Step 1 (git提取-bridge侧) ──→ Step 2 (git集成-toyoura侧)
         │
         ├──→ Step 3 (Monitor MCP化)
         │         │
         ├──→ Step 4 (Notification MCP化) ─┐
         │                                  │
         ├──→ Step 5 (Console MCP化) ───────┤
         │                                  │
         ├──→ Step 6 (checked语义) ─────────┤
         │                                  ▼
         └──────────────────────────→ Step 7 (client清理)
                                            │
                                            ▼
                                      Step 8 (workspace)
```

Step 1-6 可部分并行（1→2 串行，3/4/5/6 互不依赖但都依赖 MCP 通道可用），Step 7 必须等所有直连用户迁移完毕。

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| MCP 调用延迟影响 Console 体验 | 中 | MCP stdio ~几ms，可接受；Ctrl+B 作为逃生门 |
| git 快照非原子 | 低 | 语义是"决策时刻的状态"，MCP 调用前 commit 合理 |
| PfcMonitor 解析 MCP TextContent 复杂 | 中 | 考虑 pfc_list_tasks 返回结构化 JSON 或约定格式 |
| Foreground/Background 切换逻辑复杂 | 中 | 分步骤迁移，先 Monitor 再 Console |
| pfc-bridge 协议变更不兼容 | 低 | checked 重命名可渐进（先加 checked，再移除 notified） |

---

## 验收标准

1. `pfc-mcp/pfc-bridge/` 中无 git 相关代码（`git_version.py` 已迁走）
2. `packages/backend/` 中无 `from backend.infrastructure.pfc.client import` 语句
3. `infrastructure/pfc/client.py` 已删除
4. PFC Monitor 通过 MCP 获取任务信息
5. User Console (`>` 前缀) 通过 MCP 执行
6. `pfc_list_tasks` 返回 `checked` 字段，无 `mark_task_notified` 机制
7. 所有现有功能（Console、Ctrl+B、Monitor、Notification）正常工作

---

**Document Version**: 1.0
**Last Updated**: 2026-02-08
