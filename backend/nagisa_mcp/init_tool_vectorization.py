#!/usr/bin/env python3
"""
工具向量化初始化脚本（官方推荐list_tools方式）

- 启动MCP服务器实例
- 自动调用所有register_xxx_tools(mcp)注册函数
- 用mcp.list_tools()获取所有注册工具的详细信息
- 用ToolVectorizer统一向量化
"""

import sys
import os
import importlib
import inspect
import json
from typing import List, Dict, Any
import asyncio
from fastmcp import FastMCP, Client

# 添加backend和根目录到sys.path
backend_path = os.path.dirname(os.path.dirname(__file__))  # 回到backend目录
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.dirname(backend_path))

from nagisa_mcp.tool_vectorizer import ToolVectorizer

def import_and_register_all_tools(mcp):
    """
    自动import所有register_xxx_tools函数并注册到mcp
    """
    tool_module_paths = [
        'nagisa_mcp.tools.common_tools.tool',
        'nagisa_mcp.tools.web_search.tool',
        'nagisa_mcp.tools.coding.workspace',
        'nagisa_mcp.tools.coding.python_executor',
        'nagisa_mcp.tools.coding.file_io',
        'nagisa_mcp.tools.email_tools.tool',
        'nagisa_mcp.tools.calendar.tool',
        'nagisa_mcp.tools.text_to_image.tool',
        'nagisa_mcp.tools.contact_tools.tool',
        'nagisa_mcp.tools.places_tools.tool',
        'nagisa_mcp.tools.memory_tools.tool',
        'nagisa_mcp.tools.text_to_image.tool',
    ]
    for module_path in tool_module_paths:
        try:
            module = importlib.import_module(module_path)
            # 查找register_xxx_tools函数
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith('register_') and name.endswith('_tools'):
                    print(f"[INFO] 调用 {module_path}.{name}(mcp)")
                    obj(mcp)
        except Exception as e:
            print(f"[WARNING] Failed to import/register {module_path}: {e}")

def main():
    print("[INFO] 启动MCP服务器实例并注册所有工具...")
    mcp = FastMCP("Tool Vectorization Server")
    import_and_register_all_tools(mcp)

    async def vectorize_all_tools():
        async with Client(mcp) as client:
            tool_infos = await client.list_tools()
            print(f"[INFO] list_tools()返回 {len(tool_infos)} 个工具")

            print("[INFO] 初始化ToolVectorizer...")
            vectorizer = ToolVectorizer("tool_db")

            print("[INFO] 开始向量化...")
            for tool in tool_infos:
                try:
                    # tool是Tool对象，直接访问属性
                    name = tool.name
                    description = tool.description or ''
                    tags = getattr(tool, 'tags', []) or []
                    category = getattr(tool, 'category', '') or ''
                    parameters = getattr(tool, 'parameters', {}) or {}
                    docstring = getattr(tool, 'docstring', '') or description
                    module_name = getattr(tool, 'module', '') or ''
                    # func对象无法直接获得，只能存元数据
                    params_str = json.dumps(parameters, ensure_ascii=False, default=str)
                    # 只存元数据，不存func对象
                    vectorizer.collection.add(
                        documents=[description],
                        metadatas=[{
                            'function_name': name,
                            'module_name': module_name,
                            'category': category,
                            'tags': json.dumps(tags),
                            'parameters': params_str,
                            'return_type': getattr(tool, 'return_type', ''),
                            'docstring': docstring,
                            'registered_at': '',
                            'description': description
                        }],
                        ids=[name]
                    )
                    print(f"[DEBUG] Registered tool: {name}")
                except Exception as e:
                    print(f"[ERROR] 向量化失败: {getattr(tool, 'name', 'unknown')}: {e}")
            print("[INFO] 向量化完成！")
            print(f"[INFO] 当前数据库类别: {vectorizer.list_all_categories()}")

    asyncio.run(vectorize_all_tools())

if __name__ == "__main__":
    main() 