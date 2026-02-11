# Test Implementation Plan

## 1. pfc-mcp Contract Tests (`pfc-mcp/tests/test_tool_contracts.py`)

Mock WebSocket bridge, call tools via `mcp._tool_manager.call_tool()`, assert return字段结构。

Tests:
- `test_execute_task_success_fields` — pending 状态，必有 operation/status/task_id/entry_script/display
- `test_check_task_status_running_fields` — running 状态，必有 pagination/output/query
- `test_check_task_status_completed_fields` — completed 状态，result 字段存在
- `test_list_tasks_with_tasks_fields` — 有任务时，tasks 数组 + total_count + has_more
- `test_list_tasks_empty` — 无任务时，tasks=[], total_count=0

Pattern: 复用 test_phase3 的 mock WebSocket bridge 模式，扩展 handler 支持 pfc_task/check_task_status/list_tasks。

## 2. Backend Polling Tests (`packages/backend/tests/application/notifications/test_pfc_notification.py`)

纯单元测试，mock 掉 MCP 调用和 WebSocket 推送，验证轮询逻辑。

Tests:
- `test_polling_stops_on_terminal_state` — mock MCP 返回 completed → 验证轮询停止
- `test_status_normalization` — 直接测试 `_normalize_status` 各种输入
- `test_parse_structured_response` — 直接测试 `_parse_task_status_structured`
- `test_parse_text_response` — 直接测试 `_parse_task_status_text`
