import json

def extract_text_from_mcp_result(result):
    """
    统一提取MCP工具返回的TextContent内容，并自动结构化（如JSON）。
    支持单个TextContent、TextContent列表、字符串、dict等常见情况。
    返回结构化内容（dict/list）或纯文本。
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
    # 2. 处理单个TextContent对象
    if hasattr(result, "text") and isinstance(result.text, str):
        return try_json(result.text)
    # 3. 处理dict
    if isinstance(result, dict) and "text" in result:
        return try_json(result["text"])
    # 4. 处理字符串
    if isinstance(result, str):
        return try_json(result)
    # 5. fallback: 其他类型

    return result 