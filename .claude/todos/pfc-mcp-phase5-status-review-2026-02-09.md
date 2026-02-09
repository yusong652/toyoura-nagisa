# PFC-MCP Phase 5 实施复盘（2026-02-09）

**Created**: 2026-02-09  
**Status**: In Progress (Review Updated)

---

## 结论

本轮主线目标已经完成大半：

1. Git 快照职责已从 `pfc-bridge` 抽离到 `toyoura-nagisa`。
2. 后端已移除对 `backend.infrastructure.pfc.client` 的直连依赖（该文件已删除）。
3. `pfc_execute_code` 已接入并注册到 `pfc-mcp`，Console 主链路经 MCP 运行。

仍需继续收敛的关键项：

1. `notified -> checked` 语义迁移在 bridge 侧尚未完成。
2. workspace 单一真源策略尚未完全对齐（尚未落地到后端统一策略）。
3. 轮询状态模型、阻塞等待和 CLI 展示细节仍有优化空间。

---

## 与 2026-02-08 正交化文档对照

| Step | 状态 | 复盘 |
|------|------|------|
| Step 1: Git Version 提取（bridge 侧清理） | DONE | `pfc-mcp/pfc-bridge/server/services/git_version.py` 已移除；bridge 侧无 git 相关逻辑；`execute_task` 返回中不再含 bridge 侧 git 字段。 |
| Step 2: toyoura 侧 Git 快照集成 | DONE | `packages/backend/infrastructure/pfc/git_version.py` 已落地；`ToolExecutor` 在 `pfc_execute_task` 前置 hook 创建快照并写入本地 `PfcTaskManager`。 |
| Step 3: Backend MCP 迁移 - PfcMonitor | PARTIAL | 已去除直连 client，改为读取本地任务管理器；但并未按原计划直接在 Monitor 内调用 `pfc_list_tasks`。 |
| Step 4: Backend MCP 迁移 - NotificationService | PARTIAL | 已通过 MCP 调 `pfc_check_task_status` 同步状态；任务列表仍主要来自本地管理器。 |
| Step 5: Backend MCP 迁移 - User Console | DONE | `pfc_execute_code` 已注册并接入；Ctrl+B 通过本地前台句柄 + 轮询模式工作。 |
| Step 6: Notified -> Checked | PARTIAL | `pfc-mcp` 工具层已兼容 `checked/notified`；但 bridge 仍保留 `mark_task_notified` handler 与 `notified` 存储字段。 |
| Step 7: 清理 infrastructure/pfc | PARTIAL | `client.py` 已删除且无残留 import；`foreground_handle.py`/`foreground_registry.py` 仍保留（已转本地控制流职责）。 |
| Step 8: Workspace 路径检测 | PARTIAL | 已不依赖旧 client；但统一 workspace 真源策略（配置优先级 + MCP 回退 + 结构化失败）尚未完整收敛。 |

---

## 与 2026-02-09 Follow-ups 对照

### P0

- [ ] 统一 workspace 来源与配置策略（未完全完成）
- [ ] 本地任务持久化语义补强（重启后继续追踪远端任务语义仍需完善）
- [ ] 轮询与 agent 手动查询并发验证（需要补回归用例）

### P1

- [ ] 完成 `notified -> checked` 语义迁移（bridge 侧仍有 `mark_task_notified`）
- [ ] 轮询效率与状态确定性继续优化（`wait_seconds` 仍默认阻塞等待）
- [x] 结果适配层部分收敛：后端已统一 MCP tool result 归一化并保证 `llm_content.parts`
- [ ] CLI 展示节流与提示文案统一（尚未看到完整落地）

### P2

- [ ] 测试矩阵补齐（结构化返回 contract / 后端轮询 / CLI 状态机）
- [ ] 文档同步（`pfc-mcp/pfc-bridge/README.md` 仍有 git 旧描述）

---

## 下一轮建议执行顺序

1. **先完成语义切换**：bridge 内部把 `notified` 正式迁到 `checked`，移除 `mark_task_notified` 路由与 handler。
2. **再统一 workspace 策略**：按 `PFC_MCP_WORKSPACE_PATH -> get_working_directory -> 结构化错误` 统一后端与工具层行为。
3. **收敛轮询模型**：减少/移除 MCP 主动等待，状态标准化尽量上提到 `pfc-mcp`，后端仅做映射。
4. **最后补测试和文档**：先补 contract tests，再更新 bridge/toyoura 两侧文档，防止回归。

---

## 验收门槛（更新后）

1. 全链路不再出现 `mark_task_notified/notified` 写路径。
2. workspace 解析失败能稳定返回结构化错误（而非隐式 fallback）。
3. 后台轮询与 agent 查询并发时，无状态错判、无输出丢失。
4. README 与测试矩阵覆盖当前真实实现。
