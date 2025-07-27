import sys
from pathlib import Path

# 使用 pathlib 优雅处理路径  
_CURRENT_FILE = Path(__file__)
_NAGISA_MCP_DIR = _CURRENT_FILE.parent
_BACKEND_DIR = _NAGISA_MCP_DIR.parent

# 添加backend路径到 sys.path
sys.path.insert(0, str(_BACKEND_DIR))

from nagisa_mcp.tool_vectorizer import ToolVectorizer

if __name__ == "__main__":
    vectorizer = ToolVectorizer()  # 使用默认配置路径
    query = "image"
    print(f"[TEST] 查询关键词: {query}")
    results = vectorizer.search_tools(query, n_results=5)
    print(f"[TEST] 查到 {len(results)} 个工具：")
    for i, tool in enumerate(results, 1):
        meta = tool.get('metadata', {})
        print(f"  {i}. {meta.get('function_name', 'unknown')} | {meta.get('description', '')}")
        print(f"     类别: {meta.get('category', '')} | 标签: {meta.get('tags', '')}")
        print(f"     参数: {meta.get('parameters', '')}") 