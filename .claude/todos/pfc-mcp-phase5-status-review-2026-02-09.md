# PFC-MCP Phase 5 实施复盘（2026-02-09）

**Created**: 2026-02-09
**Status**: Complete (Final Review, 2026-02-11)

---

## 结论

本轮主线目标已全部完成：

1. Git 快照职责已从 `pfc-bridge` 抽离到 `toyoura-nagisa`。
2. 后端已移除对 `backend.infrastructure.pfc.client` 的直连依赖（该文件已删除）。
3. User Console 主链路已统一到 `pfc_execute_task` + `pfc_check_task_status`，`pfc_execute_code` 已从 MCP 侧移除。
4. `notified/checked` 语义已从 pfc-mcp/pfc-bridge 完整移除，通知追踪归属 toyoura-nagisa 后端。
5. pfc-bridge README 已完成独立化，移除所有 toyoura-nagisa 引用，准备作为独立项目。

---

## 与 2026-02-08 正交化文档对照

| Step | 状态 | 复盘 |
|------|------|------|
| Step 1: Git Version 提取（bridge 侧清理） | DONE | `pfc-mcp/pfc-bridge/server/services/git_version.py` 已移除；bridge 侧无 git 相关逻辑；`execute_task` 返回中不再含 bridge 侧 git 字段。 |
| Step 2: toyoura 侧 Git 快照集成 | DONE | `packages/backend/infrastructure/pfc/git_version.py` 已落地；`ToolExecutor` 在 `pfc_execute_task` 前置 hook 创建快照并写入本地 `PfcTaskManager`。 |
| Step 3: Backend MCP 迁移 - PfcMonitor | DONE | 已去除直连 client，改为读取本地任务管理器。 |
| Step 4: Backend MCP 迁移 - NotificationService | DONE | 已通过 MCP 调 `pfc_check_task_status` 同步状态；任务列表来自本地管理器。 |
| Step 5: Backend MCP 迁移 - User Console | DONE | 已改为 `pfc_execute_task` 提交 + `pfc_check_task_status` 轮询；`pfc_execute_code` 工具已删除。 |
| Step 6: Notified -> Checked | DONE | bridge 侧 `mark_task_notified` handler/route/field 已全部删除；pfc-mcp 工具层已移除 checked/notified 输出；通知追踪归属 toyoura-nagisa `PfcTaskManager.completion_notified`。 |
| Step 7: 清理 infrastructure/pfc | DONE | `client.py` 已删除且无残留 import；`foreground_handle.py`/`foreground_registry.py` 保留（本地控制流职责，非 pfc-mcp 职责）。 |
| Step 8: Workspace 路径检测 | DONE | `PFC_MCP_WORKSPACE_PATH` → `get_working_directory` → 结构化错误。 |

---

## 与 2026-02-09 Follow-ups 对照

### P0

- [x] 统一 workspace 来源与配置策略
- [x] 本地任务持久化语义补强（`data/pfc_tasks.json`，重启后重连远端任务，24h 超时清理）
- [x] 轮询与 agent 手动查询并发验证（后端 1s 轮询，自动启停，无回归报告）

### P1

- [x] 完成 `notified -> checked` 语义迁移（bridge 侧已完整移除）
- [x] 轮询效率与状态确定性继续优化（pfc-mcp 无状态，后端轮询自动启停）
- [x] 结果适配层部分收敛：后端已统一 MCP tool result 归一化并保证 `llm_content.parts`
- [x] MCP 工具错误语义修正：`is_error` 仅由调用层失败决定，不再由 task status（如 `failed`）反推
- [x] `pfc_check_task_status` 上下文注入修正：LLM 优先消费 `display`，避免回退到整段 JSON payload
- [x] CLI 展示节流与提示文案统一（已落地：1s 轮询推送、终态自动清除）

### P2

- [ ] 测试矩阵补齐（结构化返回 contract / 后端轮询 / CLI 状态机）
- [x] 文档同步（pfc-bridge README 已全面更新：移除 git/foreground/notified/toyoura-nagisa 引用）

---

## 本轮新增完成项（2026-02-10）

1. **移除 MCP Console 重叠工具**：`pfc_execute_code` 已从 `pfc-mcp` 完整移除（实现、注册、导出、bridge client 接口、README 文案）。
2. **统一执行参数语义**：`pfc_execute_task` 不再暴露前台参数，执行模型收敛为后台提交 + 状态轮询。
3. **修复结果污染问题**：`pfc-bridge` 执行脚本前清理全局 `result`，避免上一任务结果串到下一次 `check_status` 的 `result` 字段。

---

## 本轮新增完成项（2026-02-11）

1. **notified/checked 完整移除**：bridge 侧 `mark_task_notified` handler/route/field 已删除；pfc-mcp 工具层已移除 checked/notified 输出（commit `af65be2e`）。
2. **pfc-bridge README 全面更新**：
   - 移除 `mark_task_notified` API 文档
   - 移除 `run_in_background` / foreground task 概念（bridge 现在所有任务后台执行）
   - 移除 git snapshot 相关描述（Key Design Decisions、Response 示例、Features 章节、Troubleshooting）
   - 移除 `reset_workspace` API（handler 已删除）
   - 独立化：移除所有 toyoura-nagisa 引用，License 改为独立 MIT
3. **pfc_capture_plot 优化**：
   - docstring 改为面向 LLM（引导使用此工具而非手写 PFC plot 命令）
   - 移除 pfc-mcp 侧冗余 `_wait_local_file`（bridge 侧已确认文件存在）
   - 清理 `diagnostic_file_wait_s` 死配置

---

## 验收门槛（最终状态）

1. [x] 全链路不再出现 `mark_task_notified/notified` 写路径。
2. [x] workspace 解析失败能稳定返回结构化错误（而非隐式 fallback）。
3. [x] 后台轮询与 agent 查询并发时，无状态错判、无输出丢失。
4. [x] README 覆盖当前真实实现。
5. [ ] 测试矩阵覆盖当前真实实现。

---

## 剩余项

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P2 | 测试矩阵补齐 | contract tests / 轮询 / CLI 状态机 |
