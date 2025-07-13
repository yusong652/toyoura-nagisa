#!/usr/bin/env python3
"""
测试升级后的Calendar Tool功能
"""

import sys
import os
import asyncio
from pathlib import Path

# Add backend path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from fastmcp import FastMCP
from nagisa_mcp.tools.calendar.tool import register_calendar_tools
from nagisa_mcp.utils.tool_result import ToolResult
from pydantic import Field

def test_calendar_tool_registration():
    """测试calendar tool注册"""
    print("=== 测试 Calendar Tool 注册 ===")
    
    # 创建MCP实例
    mcp = FastMCP("Test Calendar Server")
    
    # 注册calendar tools
    register_calendar_tools(mcp)
    
    # 获取注册的工具 - 使用同步方法
    tools = mcp._registered_tools  # FastMCP内部工具字典
    tool_names = list(tools.keys())
    
    print(f"注册的工具数量: {len(tools)}")
    print(f"工具名称: {tool_names}")
    
    # 验证预期的工具已注册
    expected_tools = [
        "list_calendar_events",
        "create_calendar_event", 
        "update_calendar_event",
        "delete_calendar_event"
    ]
    
    for tool_name in expected_tools:
        if tool_name in tool_names:
            print(f"✅ {tool_name} 已注册")
        else:
            print(f"❌ {tool_name} 未注册")
    
    return tools

def test_tool_result_format():
    """测试ToolResult格式"""
    print("\n=== 测试 ToolResult 格式 ===")
    
    # 测试成功结果
    success_result = ToolResult(
        status="success",
        message="Test success message",
        llm_content={
            "operation": {"type": "test"},
            "result": {"success": True}
        },
        data={"test": "data"}
    )
    
    success_dict = success_result.model_dump()
    print(f"✅ 成功结果格式: {success_dict}")
    
    # 测试错误结果
    error_result = ToolResult(
        status="error",
        message="Test error message",
        error="Detailed error info"
    )
    
    error_dict = error_result.model_dump()
    print(f"✅ 错误结果格式: {error_dict}")

def test_calendar_tool_structure():
    """测试calendar tool结构"""
    print("\n=== 测试 Calendar Tool 结构 ===")
    
    # 测试导入
    try:
        from nagisa_mcp.tools.calendar.tool import (
            CalendarOperationType,
            EventStatus,
            EventVisibility,
            CalendarEvent,
            CalendarOperationResult,
            get_user_email,
            _validate_event_data,
            _parse_calendar_event,
            _execute_calendar_operation
        )
        print("✅ 所有核心组件导入成功")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return
    
    # 测试枚举
    print(f"✅ 操作类型枚举: {list(CalendarOperationType)}")
    print(f"✅ 事件状态枚举: {list(EventStatus)}")
    print(f"✅ 事件可见性枚举: {list(EventVisibility)}")
    
    # 测试数据验证
    warnings = _validate_event_data(
        summary="Test Event",
        start="2024-06-06T10:00:00+09:00",
        end="2024-06-06T11:00:00+09:00",
        location="Test Location",
        description="Test Description"
    )
    print(f"✅ 数据验证正常: {len(warnings)} 个警告")
    
    # 测试CalendarEvent
    event = CalendarEvent(
        id="test_id",
        summary="Test Event",
        start="2024-06-06T10:00:00+09:00",
        end="2024-06-06T11:00:00+09:00",
        location="Test Location"
    )
    event_dict = event.to_dict()
    print(f"✅ CalendarEvent创建成功: {event_dict['summary']}")

def test_docstring_quality():
    """测试docstring质量"""
    print("\n=== 测试 Docstring 质量 ===")
    
    from nagisa_mcp.tools.calendar.tool import register_calendar_tools
    
    # 创建MCP实例并注册工具
    mcp = FastMCP("Test Calendar Server")
    register_calendar_tools(mcp)
    
    # 检查每个工具的docstring
    tools = mcp._registered_tools
    for tool_name, tool_info in tools.items():
        print(f"✅ 工具 {tool_name}:")
        
        # 获取函数对象
        func = tool_info.get('function')
        if func:
            docstring = func.__doc__ or ""
            print(f"   描述长度: {len(docstring)} 字符")
            
            # 检查docstring是否包含关键部分
            has_return_value = "## Return Value" in docstring
            has_core_functionality = "## Core Functionality" in docstring
            has_strategic_usage = "## Strategic Usage" in docstring
            
            print(f"   包含Return Value: {'✅' if has_return_value else '❌'}")
            print(f"   包含Core Functionality: {'✅' if has_core_functionality else '❌'}")
            print(f"   包含Strategic Usage: {'✅' if has_strategic_usage else '❌'}")
        else:
            print(f"   ❌ 无法获取函数对象")

def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    # 创建MCP实例
    mcp = FastMCP("Test Calendar Server")
    register_calendar_tools(mcp)
    
    # 测试工具是否正确处理错误输入
    tools = mcp._registered_tools
    
    # 测试list_calendar_events工具
    if "list_calendar_events" in tools:
        print("✅ list_calendar_events 工具已注册")
        # 这里我们只测试注册情况，不测试实际调用（因为需要Google API认证）
    
    # 测试create_calendar_event工具
    if "create_calendar_event" in tools:
        print("✅ create_calendar_event 工具已注册")
        
    print("✅ 错误处理测试完成（仅测试注册情况）")

def main():
    """主测试函数"""
    print("🚀 开始测试升级后的Calendar Tool")
    print("=" * 50)
    
    try:
        # 1. 测试注册
        tools = test_calendar_tool_registration()
        
        # 2. 测试ToolResult格式
        test_tool_result_format()
        
        # 3. 测试工具结构
        test_calendar_tool_structure()
        
        # 4. 测试docstring质量
        test_docstring_quality()
        
        # 5. 测试错误处理
        test_error_handling()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 