# PFC Multimodal Diagnostic Tool Design

**Created**: 2025-12-20
**Status**: Planning
**Priority**: High

## Background

### Problem Statement
当前pfc_expert agent只能通过脚本输出预定义的调试信息（数值log），无法像工程师一样通过GUI可视化来诊断模拟状态。这导致：
1. 无法发现"未预见的异常"（颗粒聚集、边界穿透、应力异常分布等）
2. 需要预先知道"要打印什么"，信息采集不完整
3. 缺乏直观的状态判断能力

### Solution Philosophy
> "多模态的价值不是给出最终答案，而是扩展问题发现的边界"

工程师的诊断流程：
```
打开结果 → 看图（1秒判断大方向）→ 发现异常 → 针对性查数值
```

Nagisa应该具备同样的能力：视觉扫描（定性）→ 触发针对性查询（定量）

## Design Decision

### Tool vs SubAgent
**决定**: 先做工具，验证多模态能力后再考虑SubAgent

| 场景 | 方案 |
|------|------|
| "截个图看看当前状态" | 工具 |
| "从多个角度拍诊断图" | 工具（批量参数）|
| "自动找最佳视角" | 未来SubAgent |

### Documentation Strategy
**决定**: 不在command_docs中添加plot命令文档

原因：
1. 文档需要先query发现，流程长
2. 工具直接在tools列表中可见，可发现性高
3. 工具可方便集成到未来的subagent中
4. plot命令是诊断命令，不是模拟计算命令，应该抽象为专用工具

## PFC Plot Commands Reference

### View Control (`plot <name> view`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `center` | vector(x,y,z) | Camera look-at point |
| `eye` | vector(x,y,z) | Camera position |
| `distance` | float | Distance from eye to center |
| `dip` | float (degrees) | Pitch angle |
| `dip-direction` | float (degrees) | Direction angle |
| `roll` | float (degrees) | Roll angle |
| `magnification` | float | Zoom level (default 1.0) |
| `projection` | perspective/parallel | Projection mode |

### Export (`plot <name> export bitmap`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | string | Output file path (PNG default) |
| `size` | int pair | Pixel dimensions (default 1024x768) |
| `dpi` | int | Resolution |

### Example Commands
```python
# 设置视角
itasca.command('plot "Plot01" view center (0,0,0) eye (10,10,10) distance 15')
itasca.command('plot "Plot01" view dip 45 dip-direction 30')

# 导出图片
itasca.command('plot "Plot01" export bitmap filename "/path/output.png" size 1920 1080')
```

## Tool Design

### Tool Name
`pfc_capture_plot`

### Parameters

```python
@mcp.tool()
async def pfc_capture_plot(
    # 输出设置（必需）
    output_path: str,                       # 绝对路径，如 "/path/to/workspace/results/plots/stress.png"

    # Plot窗口
    plot_name: str = "Plot01",              # PFC GUI中的plot窗口名

    # 图片尺寸
    size: tuple = (1920, 1080),             # 像素尺寸

    # 视角控制（全部可选，不指定则保持当前视角）
    center: tuple = None,                   # (x, y, z) 相机看向的点
    eye: tuple = None,                      # (x, y, z) 相机位置
    distance: float = None,                 # 眼睛到中心距离
    dip: float = None,                      # 俯仰角（度）
    dip_direction: float = None,            # 方向角（度）
    roll: float = None,                     # 翻转角（度）
    magnification: float = None,            # 放大倍数
    projection: str = None,                 # "perspective" 或 "parallel"
) -> ToolResult:
    """
    Capture a screenshot of PFC plot window for visual diagnosis.

    Use this tool to visually inspect simulation state. The captured image
    can be read with the 'read' tool for multimodal analysis.

    Args:
        output_path: Absolute path for output image file (must end with .png)
            Example: "/path/to/workspace/results/plots/stress_check.png"
        plot_name: Name of the plot window in PFC GUI (default: "Plot01")
        size: Image dimensions in pixels (width, height)
        center: Camera look-at point (x, y, z)
        eye: Camera position (x, y, z)
        distance: Distance from camera to center point
        dip: View plane dip angle in degrees
        dip_direction: View plane dip direction in degrees
        roll: Camera roll angle in degrees
        magnification: Zoom level (1.0 = normal)
        projection: "perspective" or "parallel"

    Returns:
        ToolResult with output_path for subsequent read() call

    Example:
        # Capture current view
        result = pfc_capture_plot(
            output_path="/path/to/workspace/results/plots/current_state.png"
        )

        # Capture with specific angle
        result = pfc_capture_plot(
            output_path="/path/to/workspace/results/plots/stress_view.png",
            center=(0, 0, 0),
            eye=(10, 10, 10),
            distance=15
        )

        # Then read for analysis
        read(result.data["output_path"])

    Path Validation:
        - Must be absolute path
        - Must end with .png
        - Parent directory will be created if not exists
        - Path must be within allowed workspace directories
    """
```

### Return Value

```python
{
    "status": "success",
    "message": "Plot captured: stress_check.png",
    "data": {
        "output_path": "/path/to/workspace/results/plots/stress_check.png",
        "plot_name": "Plot01",
        "size": [1920, 1080],
        "view_settings": {
            "center": [0, 0, 0],
            "eye": [10, 10, 10],
            "distance": 15,
            # ... other applied settings (only non-None values)
        }
    }
}
```

### Path Validation (same as other tools)
- Must be absolute path (starts with `/` on Unix or drive letter on Windows)
- Must end with `.png`
- Parent directory will be created automatically if not exists
- Recommended location: `{workspace}/results/plots/`

## Implementation Plan

### Phase 1: Basic Tool (Current Sprint)
1. [ ] Confirm PFC GUI default plot window name
2. [ ] Create `pfc_capture_plot` tool in `backend/infrastructure/mcp/tools/pfc/`
3. [ ] Generate script with plot commands
4. [ ] Execute via existing `pfc_execute_task` mechanism (synchronous)
5. [ ] Return output path for `read()` tool

### Phase 2: Integration & Testing
1. [ ] Add tool to `pfc_expert` profile
2. [ ] Test on PFC workstation
3. [ ] Verify multimodal analysis with captured images
4. [ ] Document usage patterns

### Phase 3: Enhancement (Future)
1. [ ] Consider adding to `pfc_explorer` subagent
2. [ ] Batch capture (multiple angles)
3. [ ] Preset view configurations (front, top, side, isometric)
4. [ ] Visual SubAgent for autonomous view adjustment

## Architecture Integration

### pfc-server Side
No changes needed. Tool generates Python script with plot commands, executed via existing `script` message type.

### Backend Side
New file: `packages/backend/infrastructure/mcp/tools/pfc/pfc_capture_plot.py`

```
backend/infrastructure/mcp/tools/pfc/
├── pfc_execute_task.py
├── pfc_check_task_status.py
├── pfc_list_tasks.py
├── pfc_query_command.py
├── pfc_query_python_api.py
└── pfc_capture_plot.py    # NEW
```

### Profile Update
Add to `SUBAGENT_PFC_EXPERT_TOOLS` in `backend/domain/models/agent_profiles.py`

## Questions to Confirm (on PFC Workstation)

1. **Default plot window name in PFC GUI**: Is it "Plot01" or something else?
   - Check in PFC GUI: What's the name shown in the plot window title bar?

2. **Test plot commands**: Verify these commands work in PFC console:
   ```python
   itasca.command('plot "Plot01" view center (0,0,0)')
   itasca.command('plot "Plot01" export bitmap filename "C:/test.png" size 1920 1080')
   ```

3. **Should pfc_explorer also have this tool?** (For visual exploration without execution)

## Related Context

- Previous discussion: Multimodal analysis value for simulation diagnosis
- Key insight: "定性是雷达，定量是显微镜"
- Market analysis: No existing multimodal+simulation diagnostic tools found

---

**Next Step**: Implement on PFC workstation
