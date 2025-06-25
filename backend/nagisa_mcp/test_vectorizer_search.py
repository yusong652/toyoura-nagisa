import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from nagisa_mcp.tool_vectorizer import ToolVectorizer

if __name__ == "__main__":
    vectorizer = ToolVectorizer("tool_db")
    query = "image"
    print(f"[TEST] 查询关键词: {query}")
    results = vectorizer.search_tools(query, n_results=5)
    print(f"[TEST] 查到 {len(results)} 个工具：")
    for i, tool in enumerate(results, 1):
        meta = tool.get('metadata', {})
        print(f"  {i}. {meta.get('function_name', 'unknown')} | {meta.get('description', '')}")
        print(f"     类别: {meta.get('category', '')} | 标签: {meta.get('tags', '')}")
        print(f"     参数: {meta.get('parameters', '')}") 