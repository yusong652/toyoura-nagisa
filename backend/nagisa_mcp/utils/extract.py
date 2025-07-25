import json
from datetime import datetime

def extract_text_from_mcp_result(result):
    """
    统一提取MCP工具返回的TextContent内容，并自动结构化（如JSON）。
    支持单个TextContent、TextContent列表、字符串、dict等常见情况。
    返回结构化内容（dict/list）或纯文本。
    
    对于ToolResult格式的返回，只提取llm_content字段，忽略data字段。
    """
    def try_json(text):
        try:
            return json.loads(text)
        except Exception:
            return text

    # 1. 处理列表
    if isinstance(result, list):
        structured = []
        for item in result:
            if hasattr(item, "text") and isinstance(item.text, str):
                structured.append(try_json(item.text))
            elif isinstance(item, str):
                structured.append(try_json(item))
            elif isinstance(item, dict) and "text" in item:
                structured.append(try_json(item["text"]))
            else:
                structured.append(item)
        # 如果只有一个元素，直接返回
        if len(structured) == 1:
            return structured[0]
        return structured

    # 1.5 处理 CallToolResult 或类似对象（具有 .content 列表属性）
    # 该类型出现在 fastmcp 返回结果中，格式为 object(content=[TextContent, ...], isError=bool)
    if hasattr(result, "content") and isinstance(result.content, list):
        structured_items = []
        for item in result.content:
            # TextContent
            if hasattr(item, "type") and item.type == "text":
                text_content = try_json(getattr(item, "text", ""))
                # 如果这是一个ToolResult格式的JSON，只提取llm_content
                if isinstance(text_content, dict) and "llm_content" in text_content:
                    structured_items.append(text_content["llm_content"])
                else:
                    structured_items.append(text_content)
            # ImageContent
            elif hasattr(item, "type") and item.type == "image":
                structured_items.append({
                    "type": "image",
                    "data": getattr(item, "data", None),
                    "mime_type": getattr(item, "mimeType", None),
                })
            # EmbeddedResource 或其他
            elif hasattr(item, "type") and item.type == "resource":
                structured_items.append({
                    "type": "resource",
                    "resource": getattr(item, "resource", None),
                })
            else:
                # 尝试直接序列化未知对象
                structured_items.append(item)

        # 合并单元素简化返回
        payload = structured_items[0] if len(structured_items) == 1 else structured_items

        # 如果存在 isError 标记，包装为 dict 以便后续判断
        if getattr(result, "isError", False):
            return {
                "is_error": True,  
                "content": payload,
            }
        return payload

    # 2. 处理单个TextContent对象
    if hasattr(result, "text") and isinstance(result.text, str):
        text_content = try_json(result.text)
        # 如果这是一个ToolResult格式的JSON，只提取llm_content
        if isinstance(text_content, dict) and "llm_content" in text_content:
            return text_content["llm_content"]
        return text_content
    # 3. 处理dict
    if isinstance(result, dict) and "text" in result:
        text_content = try_json(result["text"])
        # 如果这是一个ToolResult格式的JSON，只提取llm_content
        if isinstance(text_content, dict) and "llm_content" in text_content:
            return text_content["llm_content"]
        return text_content
    # 4. 处理字符串
    if isinstance(result, str):
        text_content = try_json(result)
        # 如果这是一个ToolResult格式的JSON，只提取llm_content
        if isinstance(text_content, dict) and "llm_content" in text_content:
            return text_content["llm_content"]
        return text_content
    # 5. fallback: 其他类型

    return result

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