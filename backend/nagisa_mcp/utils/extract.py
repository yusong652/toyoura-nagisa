import json
from datetime import datetime

def extract_tool_result_from_mcp(result):
    """
    从 MCP CallToolResult 中提取 ToolResult 对象。
    
    CallToolResult 结构：
    - content: list[ContentBlock] - 包含 TextContent
    - isError: bool 
    
    我们的工具返回的 ToolResult 对象序列化在 TextContent.text 中。
    总是返回完整的字典，让调用方决定如何使用。
    """
    # 错误情况
    if result.isError:
        return {"is_error": True, "content": "Tool execution failed"}
    
    # 提取第一个 TextContent 中的 ToolResult
    text_content = result.content[0].text
    tool_result = json.loads(text_content)
    
    # 返回完整的 ToolResult 字典
    return tool_result

def ensure_future_datetime(dt: datetime, now: datetime = None) -> datetime:
    """
    如果 dt 在 now 之前，则自动补全年份为今年或明年，确保返回的时间在未来。
    """
    if now is None:
        now = datetime.now(dt.tzinfo)
    if dt >= now:
        return dt
    dt_this_year = dt.replace(year=now.year)
    if dt_this_year >= now:
        return dt_this_year
    dt_next_year = dt.replace(year=now.year + 1)
    return dt_next_year