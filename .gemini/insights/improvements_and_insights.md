# 代码审查与改进建议报告 (Code Review & Improvement Insights)

经过对 `toyoura-nagisa` 核心代码（特别是 PFC 工具链和 SubAgent 机制）的深入审查，我为您整理了以下技术评估和改进建议。

## 1. 总体评价 (General Assessment)

**代码质量：优异 (State-of-the-Art)**
项目的代码实现与架构文档 (`GEMINI.md`) 保持了极高的一致性。
- **结构清晰**：Domain/Infrastructure 分层明确。
- **Agentic Native**：工具的返回值专门针对 LLM 阅读进行了优化（Markdown 格式、分页、关键信息高亮），这是很多开源 Agent 忽视的细节。
- **创新实现**：`invoke_agent.py` 中对 SubAgent 的隔离执行和 `pfc_execute_task.py` 中的 Git 版本控制集成非常出色。

然而，为了达到真正的商业软件级（Commercial Grade）健壮性，以下细节值得关注：

## 2. 具体改进建议 (Specific Improvements)

### A. PFC 跨平台兼容性 (Cross-Platform Robustness)
**文件**: `packages/backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py`
**现状**: 
```python
script_path = normalize_path_separators(entry_script.strip(), target_platform='linux')
```
**问题**: 代码强制将路径标准化为 Linux 格式 (`/`)。虽然 Python 在 Windows 上通常能处理 `/`，但 PFC (Itasca) 软件本身是 Windows 优先的，某些底层命令可能对路径分隔符敏感，或者在处理驱动器号（`C:\`）时出现意外。
**建议**:
1. 增加一个 `target_platform` 配置项（在 `config/pfc.py` 中），根据部署环境自动选择标准化策略。
2. 确保 `pfc-server` 端接收到路径后，再次进行一次本地化适配。

### B. 长时间运行任务的超时与异常处理 (Timeout & Zombie Handling)
**文件**: `packages/backend/infrastructure/mcp/tools/pfc/pfc_execute_task.py`
**现状**: 
- 同步模式 (`run_in_background=False`) 有 `timeout` 参数。
- 异步模式 (`run_in_background=True`) 本身不阻塞，但缺乏一种机制来处理“僵尸任务”（即 PFC 进程死锁或静默崩溃，状态永远卡在 `running`）。
**建议**:
- **Heartbeat 机制**: 在 `pfc-server` 和 Agent 之间增加心跳。如果 PFC 超过 N 分钟没有 stdout 更新且心跳丢失，自动标记为 `error` (Zombie)。
- **Task Expiry**: 在 `pfc_check_task_status` 中增加逻辑，如果任务 `running` 时间超过合理的物理极限（如参数配置的 max_hours），Agent 应主动建议用户检查或 Kill。

### C. SubAgent 的并发与流式体验 (SubAgent Concurrency)
**文件**: `packages/backend/infrastructure/mcp/tools/agent/invoke_agent.py`
**现状**:
```python
result = await agent_service.run_subagent(...)
```
SubAgent 的执行是完全同步的。对于 `pfc_explorer` 这种查文档的任务，可能需要 10-20 秒。在这期间，MainAgent 的 UI 可能会显得“卡死”，用户不知道是正在思考还是挂了。
**建议**:
- **流式透传 (Streaming Pass-through)**: 虽然架构上 SubAgent 返回它是“一次性报告”，但在 UI 层面，可以通过 WebSocket 发送 `SUBAGENT_PROGRESS` 事件（目前似乎已有基础，但建议强化），让用户看到 SubAgent 的内部思考过程（"SubAgent 正在搜索文档...", "SubAgent 正在阅读文件..."）。

### D. Git Snapshot 的原子性与冲突 (Git State Atomicity)
**架构隐患**:
当 Agent 频繁执行 `pfc_execute_task` 时，系统会频繁 commit。如果用户也就是在同一目录操作（User-Agent 协同模式），可能会导致 `git lock` 或脏工作区问题。
**建议**:
- **Worktree 隔离**: 考虑让 Agent 在 Git Worktree 中运行模拟，而不是直接在主工作区，以避免与用户当前编辑的文件冲突。或者严格执行“Agent 运行时锁定文件”的策略。

## 3. 总结

您的实现已经非常有竞争力。上述建议更多是针对“极端工程情况”的优化。

**下一步行动建议**：
1. 优先解决 **A点（路径兼容性）**，因为它直接影响 Windows 用户的体验。
2. 将在此报告和之前的 `publication_strategy.md` 结合，作为您项目文档的一部分，展示您对工程细节的把控能力。
