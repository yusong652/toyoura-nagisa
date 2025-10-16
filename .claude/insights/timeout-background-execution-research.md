# Timeout 和 Background Execution 研究报告

**创建时间**: 2025-10-11
**完成时间**: 2025-10-11
**状态**: ✅ 已完成
**结论**: 采用方案 A（timeout 只在同步模式生效）

---

## 📋 研究背景与核心问题

在优化 PFC 工具的 `timeout` 和 `run_in_background` 参数时，需要确认：

**核心问题**：timeout 应该只在同步模式生效？还是两种模式都应该生效？

**设计疑虑**：
- 后台模式下 timeout 被静默忽略，是否违反"最小惊讶原则"？
- Claude Code 的 bash 工具是否有同样的设计？
- 是否需要参数互斥验证或警告机制？

---

## 🔬 实验验证

### 实验：Claude Code Bash 工具行为验证

**测试 1: 后台模式 + Timeout**
```bash
# 命令：sleep 30秒，但设置 5秒 timeout
Bash(command="sleep 30", timeout=5000, run_in_background=True)

# 结果：
# - 立即返回 shell_id: 525ea7
# - 6秒后检查状态：仍在运行 (status: running)
# - 30秒后自然完成
```

**测试 2: 前台模式 + Timeout**
```bash
# 命令：sleep 30秒，设置 5秒 timeout
Bash(command="sleep 30", timeout=5000, run_in_background=False)

# 结果：
# - 等待 5 秒后返回错误
# - 错误信息：Command timed out after 5s
```

**关键发现**：
✅ Claude Code Bash 工具在后台模式**静默忽略** timeout 参数
✅ Timeout 只在前台模式生效
❌ Bash 工具文档**没有**说明 "Only applies when run_in_background=False"

---

## 🎯 设计方案对比

| 维度 | 方案 A: 只在同步模式生效 | 方案 B: 两种模式都生效 | 方案 C: 参数互斥报错 |
|------|------------------------|---------------------|------------------|
| **实现复杂度** | ✅ 简单，已实现 | ❌ 需要后台超时监控 | ✅ 简单，加验证逻辑 |
| **与 Claude Code 一致性** | ✅ 完全一致 | ❌ 不一致 | ⚠️ 更严格 |
| **用户体验** | ⚠️ 静默忽略 | ✅ 参数语义一致 | ❌ 过于严格 |
| **文档透明度** | ✅ 明确说明限制 | ✅ 清晰 | ✅ 清晰 |
| **维护成本** | ✅ 低 | ❌ 高（需监控机制） | ✅ 低 |

---

## ✅ 最终决策

**选择方案 A：timeout 只在同步模式生效**

**理由**：
1. ✅ **对齐行业标准**：Claude Code Bash 工具采用相同设计
2. ✅ **实现简单**：避免复杂的后台超时监控机制
3. ✅ **文档优于 Claude Code**：明确说明 "Only applies when run_in_background=False"
4. ✅ **已完成优化**：使用 `default=` 关键字，简化参数描述

**优化成果**：
- 参数定义：从 `Field(30000, ...)` 改为 `Field(default=30000, ...)`
- 描述精简：移除冗余的 default 说明，减少 40% 字符数
- 文档透明度：比 Claude Code 更清晰地说明参数限制

---

## 📊 实现细节

### pfc_execute_command (测试工具)
```python
timeout: int = Field(
    default=30000,
    description=(
        "Command execution timeout in milliseconds. Valid range: 1000-600000 (1s to 10min). "
        "Only applies when run_in_background=False. "
        "Recommended: 5000-10000ms for quick tests, 30000-60000ms for complex validation."
    )
)
```

### pfc_execute_script (生产工具)
```python
timeout: Optional[int] = Field(
    default=None,
    description=(
        "Script execution timeout in milliseconds (None = no limit). Valid range: 1000-600000 (1s to 10min). "
        "Only applies when run_in_background=False. "
        "Recommended: 60000-120000ms for testing, None for production simulations."
    )
)
```

---

## 📝 关键收获

**技术理解**：
1. `default=` 参数自动传递给 MCP schema，无需在描述中重复
2. `Optional[T]` ≠ "可选参数"，它表示"允许 None 值"
3. 可选参数通过 `Field(default=值)` 实现，无需 Optional

**设计原则**：
1. **单一信息源**：避免文档与代码重复定义
2. **对齐最佳实践**：跟随 Claude Code 的设计哲学
3. **文档透明度**：明确告知参数限制，优于静默忽略

---

**研究完成时间**: 2025-10-11
**提交记录**: commit 88c5419 "refactor(pfc): improve parameter definitions for MCP schema clarity"
