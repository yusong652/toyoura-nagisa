#!/usr/bin/env python3
"""
Tool vectorization initialization script using the official list_tools approach.

This script performs the following operations:
- Starts an MCP server instance
- Automatically imports and calls all register_xxx_tools(mcp) functions
- Uses mcp.list_tools() to get detailed information about all registered tools
- Vectorizes all tools using ToolVectorizer (excluding meta tools)
"""

import sys
import os
import importlib
import inspect
import json
from typing import List, Dict, Any
import asyncio
from pathlib import Path
from fastmcp import FastMCP, Client

# Use pathlib for elegant path handling
_CURRENT_FILE = Path(__file__)
_PROJECT_ROOT = _CURRENT_FILE.parent.parent  # Project root directory (scripts/../)
_BACKEND_DIR = _PROJECT_ROOT / "backend"      # Backend directory

# Add necessary paths to sys.path
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.infrastructure.mcp.tool_vectorizer import ToolVectorizer
from backend.shared.utils.tool_utils import is_meta_tool

def import_and_register_all_tools(mcp):
    """
    Automatically import all register_xxx_tools functions and register them with MCP.
    """
    tool_module_paths = [
        # Core tool suites
        'backend.infrastructure.mcp.tools.builtin',  # builtin tools including web search
        'backend.infrastructure.mcp.tools.coding.tools',  # aggregated coding tools
        'backend.infrastructure.mcp.tools.email_tools.tool',
        'backend.infrastructure.mcp.tools.calendar.tool',
        'backend.infrastructure.mcp.tools.text_to_image.tool',
        'backend.infrastructure.mcp.tools.contact_tools.tool',
        'backend.infrastructure.mcp.tools.places_tools.tool',
        'backend.infrastructure.mcp.tools.location_tool.tool',
        'backend.infrastructure.mcp.tools.memory_tools.tool',
        'backend.infrastructure.mcp.tools.calculator_tool.tool',
        'backend.infrastructure.mcp.tools.weather_tool.tool',
        'backend.infrastructure.mcp.tools.meta_tool.tool',
        'backend.infrastructure.mcp.tools.time_tool.tool',
    ]
    for module_path in tool_module_paths:
        try:
            module = importlib.import_module(module_path)
            # Find register_xxx_tools functions
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith('register_') and name.endswith('_tools'):
                    print(f"[INFO] Calling {module_path}.{name}(mcp)")
                    obj(mcp)
        except Exception as e:
            print(f"[WARNING] Failed to import/register {module_path}: {e}")

def main():
    print("[INFO] Starting MCP server instance and registering all tools...")
    mcp = FastMCP("Tool Vectorization Server")
    import_and_register_all_tools(mcp)

    async def vectorize_all_tools():
        async with Client(mcp) as client:
            tool_infos = await client.list_tools()
            print(f"[INFO] list_tools() returned {len(tool_infos)} tools")

            print("[INFO] Initializing ToolVectorizer...")
            vectorizer = ToolVectorizer()  # Use default config path (backend/tool_db)

            print("[INFO] Starting vectorization...")
            for tool in tool_infos:
                try:
                    # Tool is a Tool object, access attributes directly
                    name = tool.name
                    
                    # Skip meta tools - they should not be vectorized
                    if is_meta_tool(name):
                        print(f"[INFO] Skipping meta tool: {name} (not vectorized)")
                        continue
                    
                    description = tool.description or ''
                    module_name = getattr(tool, 'module', '') or ''
                    
                    # Extract tags and category from annotations
                    annotations = getattr(tool, 'annotations', None)
                    tags = []
                    category = ''
                    
                    if annotations:
                        # ToolAnnotations is a Pydantic BaseModel, access attributes directly
                        category = getattr(annotations, 'category', '')
                        tags = getattr(annotations, 'tags', []) or []
                        
                        # If not found, try to get from model_extra (Pydantic extra fields)
                        if not category or not tags:
                            model_extra = getattr(annotations, 'model_extra', {})
                            if not category:
                                category = model_extra.get('category', '')
                            if not tags:
                                tags = model_extra.get('tags', []) or []
                    
                    # Infer category from module_name if not provided
                    if not category:
                        if module_name.startswith('mcp.tools.'):
                            # Take the first-level directory after 'tools.', e.g., mcp.tools.coding.workspace -> coding
                            parts = module_name.split('.')
                            try:
                                idx = parts.index('tools')
                                if idx + 1 < len(parts):
                                    category = parts[idx + 1]
                            except ValueError:
                                pass
                    if not category and tags:
                        category = list(tags)[0]
                    if not category:
                        category = 'general'
                    
                    # Get parameter information - FastMCP uses inputSchema instead of parameters
                    input_schema = getattr(tool, 'inputSchema', {}) or {}
                    docstring = getattr(tool, 'docstring', '') or description
                    # Function object cannot be obtained directly, only store metadata
                    params_str = json.dumps(input_schema, ensure_ascii=False, default=str)
                    # Only store metadata, not function objects
                    vectorizer.collection.add(
                        documents=[description],
                        metadatas=[{
                            'function_name': name,
                            'module_name': module_name,
                            'category': category,
                            'tags': json.dumps(list(tags)),
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
                    print(f"[ERROR] Vectorization failed: {getattr(tool, 'name', 'unknown')}: {e}")
            print("[INFO] Vectorization completed!")
            print(f"[INFO] Current database categories: {vectorizer.list_all_categories()}")

    asyncio.run(vectorize_all_tools())

if __name__ == "__main__":
    main() 