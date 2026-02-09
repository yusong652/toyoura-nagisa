# PFC-MCP Phase 5 Follow-ups (2026-02-09)

## 背景

本轮已经完成：
- `pfc_execute_task / pfc_check_task_status / pfc_list_tasks` 成功路径结构化返回（保留 `display`）
- 后端轮询优先读取 `structuredContent`，文本解析仅 fallback
- pfc-bridge 残留 git 启动逻辑清理（git 版本追踪归属 toyoura-nagisa）

当前仍有若干“功能可用但不够优雅/稳健”的后续事项，需要继续收敛。

---

## P0（高优先级，建议优先完成）

- [ ] **统一 workspace 来源与配置策略**
  - 现状：部分链路不再向 PFC GUI 请求工作目录，workspace 来源不统一
  - 目标：定义单一真源（配置优先级 + 运行时回退）
  - 建议顺序：
    1. `PFC_MCP_WORKSPACE_PATH`（显式配置）
    2. MCP `get_working_directory`（可用时）
    3. 安全回退（拒绝执行并返回结构化错误）

- [ ] **本地任务持久化语义补强**
  - 确保 task_id 在重启后仍可追踪（统一 ID 空间，无 local/remote 映射）
  - 任务恢复后可继续轮询并正确推送终态与输出

- [ ] **PFC 轮询与 Agent 查询互不干扰验证**
  - 明确并测试 `pfc_check_task_status` 为“窗口化快照查询”语义
  - 增加并发场景回归：后台轮询 + agent 手动查询同时进行

---

## P1（中优先级，近期完成）

- [ ] **完成 notified -> checked 语义迁移**
  - bridge 中去掉 `mark_task_notified` 路由和相关字段
  - `pfc_check_task_status` 查询终态时隐式标记 `checked`
- [ ] **优化后端轮询效率与状态确定性**
  - **状态模型标准化**：在 pfc-mcp 内部使用严格的 Status Enum，外部输出统一的规范化字符串（Success, Running, Failed...），从后端移除正则表达式猜测逻辑。
  - **分段式双截断策略 (Dual Truncation)**：
    - **MCP 层**：维持工具的“无状态”快照语义，仅对过长的总输出进行长度截断（Snapshot Truncation），确保单次调用响应不超时，并优先保证多客户端可见。
    - **后端服务层**：实施“窗口截断”渲染逻辑，通过分页/滚动加载决定最终展示内容。
  - **减少同步阻塞延迟**：移除或大幅减小轮询请求中的主动等待参数 (wait_seconds)，改由应用层控制流控制。

- [ ] **后端结果适配层进一步收敛**
  - 抽离 MCP raw -> internal ToolResult adapter（避免散落在多处）
  - 约束所有 tool result 必须带有效 `llm_content.parts`

- [ ] **CLI 展示体验优化**
  - 完成态的自动消失节流策略（避免闪烁）
  - 输出区分页/截断提示与“查看更新”引导文案统一

---

## P2（低优先级，质量提升）

- [ ] **补齐测试矩阵**
  - MCP 工具结构化返回 contract tests
  - 后端轮询同步 tests（structuredContent 优先 + text fallback）
  - CLI 状态机 tests（running -> terminal -> clear）

- [ ] **文档同步**
  - 更新 `pfc-mcp/pfc-bridge/README.md`：移除 git 相关描述
  - 更新 toyoura-nagisa 侧开发文档：workspace 策略、任务映射、轮询语义

---

## 验收门槛（下一阶段）

1. workspace 解析策略在后端/CLI/工具层一致，且有失败时结构化错误
2. 后台轮询与 agent 查询并发时，无输出丢失、无状态错判
3. `mark_task_notified` 全链路移除，仅保留 `checked` 语义
4. 关键链路有最小回归测试保护
