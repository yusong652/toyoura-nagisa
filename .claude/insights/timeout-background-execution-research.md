# Timeout 和 Background Execution 深度研究计划

**创建时间**: 2025-10-11
**状态**: 待研究
**优先级**: 高

---

## 📋 研究背景

在优化 PFC 工具的 `timeout` 和 `run_in_background` 参数时，发现了以下问题：

### 当前实现的困惑
1. **参数语义不清晰**：timeout 在 `run_in_background=True` 时应该表示什么？
2. **参数被静默忽略**：后台模式下 timeout 被完全忽略，无任何警告
3. **与 Bash 工具行为一致**：Claude Code 的 bash 工具也有同样的设计

### 核心问题
> **timeout 应该只在同步模式生效？还是两种模式都应该生效？**

---

## 🎯 研究目标

### 1. 理解 Claude Code Bash 工具的设计哲学
- [ ] 深入研究 `background_process_manager.py` 的实现
- [ ] 理解为什么 timeout 在后台模式被忽略
- [ ] 验证后台任务是否有其他超时控制机制

### 2. 验证不同工具的行为
- [ ] 测试 bash 工具在不同参数组合下的实际行为
- [ ] 测试 bash 后台任务是否会被系统自动清理
- [ ] 检查是否有全局的后台任务超时配置

### 3. 确定 PFC 工具的最佳设计
- [ ] 评估"timeout 两种模式都生效"的可行性
- [ ] 评估"timeout 只在同步模式生效"的合理性
- [ ] 对比不同方案的用户体验

---

## 🧪 实验计划

### 实验 1: Bash 后台任务的生命周期

**目标**: 了解后台任务如何被管理和清理

```bash
# 步骤 1: 启动一个长时间后台任务
bash(command="sleep 300", run_in_background=True, timeout=5000)
# 预期：返回 process_id，timeout 被忽略

# 步骤 2: 等待 10 秒后检查进程状态
sleep 10
ps aux | grep "sleep 300"  # 进程应该还在运行

# 步骤 3: 检查 process_manager 是否有清理机制
# 研究 background_process_manager.py 中的：
# - PROCESS_TIMEOUT_HOURS
# - cleanup 机制
# - 进程监控逻辑
```

**关键问题**：
- 后台任务是否有默认的最大存活时间？
- 超时清理是否依赖 process_manager？
- 用户如何手动终止失控的后台任务？

---

### 实验 2: 深入研究 background_process_manager

**目标**: 理解后台任务管理的完整机制

**研究文件**:
```
backend/infrastructure/mcp/tools/coding/utils/background_process_manager.py
```

**需要回答的问题**:
1. ✅ 后台任务是否有超时控制？
   - 检查 `start_process()` 方法
   - 检查 `_cleanup_old_processes()` 方法

2. ✅ timeout 参数为什么被忽略？
   - 设计决策的原因是什么？
   - 是技术限制还是产品设计？

3. ✅ 如何终止失控的后台任务？
   - `kill_shell()` 工具的实现
   - 进程强制终止的机制

---

### 实验 3: 对比不同设计方案

**方案 A**: timeout 只在同步模式生效（当前实现）

```python
# 同步模式
timeout=30000, run_in_background=False
→ 等待30秒，超时返回错误 ✓

# 异步模式
timeout=30000, run_in_background=True
→ 立即返回 task_id，timeout 被忽略 ⚠️
```

**优点**:
- 实现简单，与 Bash 工具一致
- 避免复杂的后台超时管理

**缺点**:
- 参数语义不一致，容易困惑
- 无法控制后台任务的最大执行时间
- 参数被静默忽略，违反最小惊讶原则

---

**方案 B**: timeout 两种模式都生效

```python
# 同步模式
timeout=30000, run_in_background=False
→ 等待30秒，超时返回错误 ✓

# 异步模式
timeout=30000, run_in_background=True
→ 返回 task_id，后台任务30秒后自动终止 ✓
```

**优点**:
- 参数语义一致，符合直觉
- 提供后台任务的安全保障
- 避免失控的长时间任务

**缺点**:
- 需要在 TaskManager 中实现超时监控
- PFC 命令在 main thread 执行，cancel 可能不生效
- 增加系统复杂度

---

**方案 C**: 参数互斥 + 明确报错

```python
# 允许：只设置一个参数
timeout=30000, run_in_background=False  ✓
timeout=None, run_in_background=True     ✓

# 拒绝：同时设置两个参数
timeout=30000, run_in_background=True
→ 返回错误："timeout 在后台模式不适用" ✗
```

**优点**:
- 避免参数困惑，明确告知用户
- 强制用户理解两种模式的区别

**缺点**:
- 过于严格，限制灵活性
- 用户可能期望 timeout 控制后台任务

---

### 实验 4: PFC 特殊性的技术验证

**目标**: 验证 PFC 命令的超时控制可行性

**技术挑战**:
```python
# PFC 命令在 IPython main thread 队列中执行
future = main_executor.submit(
    lambda: itasca.command("model cycle 50000")
)

# 问题：future.cancel() 能否中断正在执行的命令？
asyncio.create_task(cancel_after_timeout(future, timeout_ms))
```

**验证步骤**:
1. 创建一个长时间 PFC 命令（如 `model cycle 100000`）
2. 提交到 main_executor 队列
3. 在外部尝试 cancel future
4. 观察命令是否真的被中断

**预期结果**:
- ❌ future.cancel() 可能**无法**中断已经开始执行的命令
- 原因：Python 的 asyncio.Future.cancel() 只能取消未开始的任务
- 结论：需要在 PFC 层面实现超时控制（例如在脚本中检查时间）

---

## 🔍 深入研究 Background Process Manager

### 需要回答的关键问题

#### 1. 进程清理机制
```python
# background_process_manager.py
PROCESS_TIMEOUT_HOURS = ?  # 后台任务的默认存活时间是多久？

def _cleanup_old_processes(self):
    # 如何判断"旧"进程？
    # 基于时间？基于状态？
    pass
```

#### 2. 超时参数的设计决策
- 为什么 `start_process()` 不接收 timeout 参数？
- 是否有文档说明这个设计决策？
- Claude Code 团队的设计意图是什么？

#### 3. 用户如何控制后台任务
- `kill_shell(process_id)` 的实现机制
- 是否有批量清理的工具？
- 用户如何查看所有运行中的后台任务？

---

## 📝 实验记录模板

### 实验日期: YYYY-MM-DD
### 实验人员: [姓名]
### 实验目标: [简述]

#### 实验步骤
1. [步骤1]
2. [步骤2]
3. [步骤3]

#### 实验结果
- **观察现象**: [描述]
- **实际行为**: [描述]
- **与预期的差异**: [描述]

#### 关键发现
- 发现 1: [描述]
- 发现 2: [描述]

#### 遗留问题
- [ ] 问题 1
- [ ] 问题 2

---

## 🎯 决策标准

完成研究后，根据以下标准选择最佳方案：

### 1. 用户体验 (40%)
- 参数语义是否清晰？
- 是否符合用户直觉？
- 错误提示是否友好？

### 2. 技术可行性 (30%)
- 实现复杂度如何？
- 是否有技术风险？
- 维护成本如何？

### 3. 一致性 (20%)
- 是否与 Bash 工具一致？
- 是否符合 Claude Code 设计哲学？
- 是否与 PFC 工具体系统一？

### 4. 安全性 (10%)
- 是否能防止失控任务？
- 是否有资源泄漏风险？
- 错误处理是否完善？

---

## 📅 研究时间表

- **Day 1**: 实验 1-2，理解现有机制
- **Day 2**: 实验 3-4，验证技术可行性
- **Day 3**: 总结分析，做出设计决策
- **Day 4**: 实现和测试选定方案

---

## 📌 待办事项

### 立即执行
- [ ] 阅读 `background_process_manager.py` 完整源码
- [ ] 测试 bash 后台任务的实际超时行为
- [ ] 验证 PFC future.cancel() 的有效性

### 后续任务
- [ ] 编写完整的测试用例
- [ ] 更新工具文档
- [ ] 同步 PFC Expert Prompt

---

## 💡 临时笔记区

### 2025-10-11 初步发现
1. Bash 工具确实在后台模式忽略 timeout 参数
2. 当前没有明确的参数冲突警告
3. 需要深入研究 process_manager 的清理机制

### 待确认的假设
- ❓ 假设：后台任务依赖系统的进程管理，不需要 timeout
- ❓ 假设：timeout 只是"等待时间"，不是"执行时间"
- ❓ 假设：PFC 命令无法被 future.cancel() 中断

---

## 🔗 相关资源

- Claude Code 文档: https://docs.claude.com/claude-code
- PFC 工具实现: `backend/infrastructure/mcp/tools/pfc/`
- Task Manager: `pfc_workspace/pfc_server/task_manager.py`
- Background Process Manager: `backend/infrastructure/mcp/tools/coding/utils/background_process_manager.py`

---

**最后更新**: 2025-10-11
**下次审查**: 明天继续研究实验计划
