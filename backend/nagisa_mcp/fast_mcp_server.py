import asyncio
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Client
from datetime import datetime

mcp = FastMCP("Fast MCP Server")

# 工具函数定义
@mcp.tool()
async def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
async def calculate(expression: str) -> float:
    """计算数学表达式"""
    try:
        # 使用 eval 计算表达式，但限制只能使用基本数学运算
        allowed_chars = set('0123456789+-*/(). ')
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Expression contains invalid characters")
        return eval(expression)
    except Exception as e:
        raise ValueError(f"Invalid expression: {str(e)}")

@mcp.tool()
async def search_weather(city: str) -> Dict[str, Any]:
    """模拟天气查询"""
    # 这里只是模拟数据，实际应用中应该调用真实的天气 API
    weather_data = {
        "北京": {"temperature": 25, "condition": "晴", "humidity": 40},
        "上海": {"temperature": 28, "condition": "多云", "humidity": 60},
        "广州": {"temperature": 30, "condition": "雨", "humidity": 80}
    }
    if city in weather_data:
        return weather_data[city]
    raise ValueError(f"City {city} not found")

@mcp.tool()
async def translate_text(text: str, target_language: str) -> str:
    """模拟文本翻译"""
    # 这里只是模拟翻译，实际应用中应该调用真实的翻译 API
    translations = {
        "你好": {
            "en": "Hello",
            "ja": "こんにちは",
            "ko": "안녕하세요"
        }
    }
    if text in translations and target_language in translations[text]:
        return translations[text][target_language]
    return f"[Translation not available for {text} to {target_language}]"

# 启动服务器
if __name__ == "__main__":
    print("Starting Fast MCP Server with function call support...")
    mcp.run()

