import json
from datetime import datetime

def extract_tool_result_from_mcp(result):
    """
    从 MCP CallToolResult 中提取 ToolResult 对象。
    
    CallToolResult 结构：
    - content: list[ContentBlock] - 包含 TextContent
    - isError: bool 
    
    我们的工具返回的 ToolResult 对象序列化在 TextContent.text 中。
    所有工具都通过 ToolResult.model_dump() 返回规范的 JSON，因此不需要错误处理。
    """
    # 提取并解析 TextContent 中的 ToolResult JSON
    text_content = result.content[0].text
    tool_result = json.loads(text_content)
    
    # 如果 MCP 标记为错误，确保设置 is_error 标志
    if result.isError:
        tool_result["is_error"] = True
        
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