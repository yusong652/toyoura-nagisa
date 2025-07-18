#!/usr/bin/env python3
"""
检查所有工具模块的向量化情况
"""

import sys
import inspect
import importlib
from typing import List, Dict, Any
from pathlib import Path

# 使用 pathlib 优雅处理路径
_CURRENT_FILE = Path(__file__)
_NAGISA_MCP_DIR = _CURRENT_FILE.parent  # nagisa_mcp目录
_BACKEND_DIR = _NAGISA_MCP_DIR.parent   # backend目录  
_PROJECT_ROOT = _BACKEND_DIR.parent     # 项目根目录

# 添加必要路径到 sys.path
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.nagisa_mcp.tool_vectorizer import ToolVectorizer

def get_all_tool_modules() -> Dict[str, Dict[str, Any]]:
    """获取所有工具模块的配置"""
    return {
        'builtin': {
            'module_path': 'nagisa_mcp.tools.builtin',
            'category': 'information',
            'tags': ['search', 'web', 'information', 'lookup', 'builtin'],
            'description': 'Built-in tools including web search and information retrieval'
        },
        'coding': {
            'module_path': 'nagisa_mcp.tools.coding.tools',
            'category': 'development',
            'tags': ['code', 'programming', 'file', 'workspace', 'python'],
            'description': 'Coding and development tools'
        },
        'email_tools': {
            'module_path': 'nagisa_mcp.tools.email_tools.tool',
            'category': 'communication',
            'tags': ['email', 'mail', 'communication', 'gmail'],
            'description': 'Email management and communication tools'
        },
        'calendar': {
            'module_path': 'nagisa_mcp.tools.calendar.tool',
            'category': 'scheduling',
            'tags': ['calendar', 'schedule', 'events', 'time_management'],
            'description': 'Calendar and scheduling management tools'
        },
        'text_to_image': {
            'module_path': 'nagisa_mcp.tools.text_to_image.tool',
            'category': 'media',
            'tags': ['image', 'generation', 'art', 'visual'],
            'description': 'Text-to-image generation tools'
        },
        'contact_tools': {
            'module_path': 'nagisa_mcp.tools.contact_tools.tool',
            'category': 'communication',
            'tags': ['contacts', 'people', 'address_book', 'communication'],
            'description': 'Contact management tools'
        },
        'places_tools': {
            'module_path': 'nagisa_mcp.tools.places_tools.tool',
            'category': 'places',
            'tags': ['places', 'maps', 'geography'],
            'description': 'Places and POI search tools'
        },
        'location_tools': {
            'module_path': 'nagisa_mcp.tools.location_tool.tool',
            'category': 'location',
            'tags': ['location', 'geolocation', 'coordinates'],
            'description': 'Location retrieval utilities'
        },
        'memory_tools': {
            'module_path': 'nagisa_mcp.tools.memory_tools.tool',
            'category': 'memory',
            'tags': ['memory', 'storage', 'recall', 'knowledge'],
            'description': 'Memory and knowledge management tools'
        },
        'google_auth': {
            'module_path': 'nagisa_mcp.tools.google_auth.oauth',
            'category': 'authentication',
            'tags': ['google', 'oauth', 'auth', 'login'],
            'description': 'Google OAuth authentication tools'
        }
    }

def check_module_tools(module_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """检查单个模块的工具情况"""
    result = {
        'module_name': module_name,
        'import_success': False,
        'tools_found': 0,
        'tools_list': [],
        'error': None
    }
    
    try:
        # 尝试导入模块
        module = importlib.import_module(config['module_path'])
        result['import_success'] = True
        
        # 查找模块中的工具函数
        tools = []
        
        # 1. 查找模块级别的工具函数
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # 跳过内部函数和导入的函数
            if name.startswith('_') or obj.__module__ != module.__name__:
                continue
                
            # 检查函数是否有文档字符串
            if obj.__doc__ and len(obj.__doc__.strip()) > 10:
                # 检查函数签名
                sig = inspect.signature(obj)
                if len(sig.parameters) > 0:
                    # 跳过一些明显不是工具的函数
                    if name in ['Field', 'load_dotenv', 'build', 'register_builtin_tools', 
                               'register_email_tools', 'register_calendar_tools', 
                               'register_coding_tools', 'register_text_to_image_tool',
                               'register_contact_tools', 'register_places_tools', 
                               'register_memory_tools', 'register_google_auth_tools',
                               'get_credentials', 'authenticate_user', 'refresh_token']:
                        continue
                    
                    # 检查函数源代码，看是否有@mcp.tool()装饰器
                    try:
                        source = inspect.getsource(obj)
                        if '@mcp.tool()' in source or '@mcp.tool(' in source:
                            tools.append({
                                'name': name,
                                'docstring': obj.__doc__.strip()[:100] + "..." if len(obj.__doc__.strip()) > 100 else obj.__doc__.strip(),
                                'parameters': len(sig.parameters),
                                'is_mcp_tool': True,
                                'location': 'module_level'
                            })
                    except Exception as e:
                        # 如果无法获取源代码，跳过
                        print(f"[WARNING] Cannot get source for {name}: {e}")
                        continue
        
        # 2. 查找注册函数内部的工具函数
        register_functions = [
            'register_builtin_tools', 'register_email_tools', 'register_calendar_tools',
            'register_coding_tools', 'register_text_to_image_tool', 'register_contact_tools',
            'register_places_tools', 'register_location_tools', 'register_memory_tools', 'register_google_auth_tools'
        ]
        
        for register_func_name in register_functions:
            if hasattr(module, register_func_name):
                register_func = getattr(module, register_func_name)
                try:
                    # 获取注册函数的源代码
                    source = inspect.getsource(register_func)
                    
                    # 查找@mcp.tool()装饰的函数
                    lines = source.split('\n')
                    current_func_name = None
                    current_docstring = ""
                    
                    for i, line in enumerate(lines):
                        line = line.strip()
                        
                        # 查找@mcp.tool()装饰器
                        if '@mcp.tool()' in line or '@mcp.tool(' in line:
                            # 下一行应该是函数定义
                            if i + 1 < len(lines):
                                func_line = lines[i + 1].strip()
                                if func_line.startswith('def '):
                                    # 提取函数名
                                    func_name = func_line.split('def ')[1].split('(')[0].strip()
                                    current_func_name = func_name
                                    
                                    # 查找函数文档字符串
                                    for j in range(i + 2, len(lines)):
                                        doc_line = lines[j].strip()
                                        if doc_line.startswith('"""') or doc_line.startswith("'''"):
                                            # 找到文档字符串开始
                                            doc_start = j
                                            for k in range(j + 1, len(lines)):
                                                if '"""' in lines[k] or "'''" in lines[k]:
                                                    # 找到文档字符串结束
                                                    doc_lines = lines[doc_start:k+1]
                                                    current_docstring = '\n'.join(doc_lines)
                                                    break
                                            break
                                    
                                    if current_func_name and current_docstring:
                                        tools.append({
                                            'name': current_func_name,
                                            'docstring': current_docstring[:100] + "..." if len(current_docstring) > 100 else current_docstring,
                                            'parameters': 0,  # 简化处理
                                            'is_mcp_tool': True,
                                            'location': f'inside_{register_func_name}'
                                        })
                                        print(f"[DEBUG] Found tool in {register_func_name}: {current_func_name}")
                                        current_func_name = None
                                        current_docstring = ""
                except Exception as e:
                    print(f"[WARNING] Cannot analyze {register_func_name}: {e}")
                    continue
        
        result['tools_found'] = len(tools)
        result['tools_list'] = tools
        
    except Exception as e:
        result['error'] = str(e)
    
    return result

def check_vectorized_tools(vectorizer: ToolVectorizer) -> Dict[str, Any]:
    """检查已向量化的工具"""
    try:
        # 获取所有已注册的工具
        all_tools = vectorizer.collection.get()
        
        # 按模块分组
        tools_by_module = {}
        for i, metadata in enumerate(all_tools['metadatas']):
            if metadata:
                module_name = metadata.get('module_name', 'unknown')
                function_name = metadata.get('function_name', 'unknown')
                category = metadata.get('category', 'unknown')
                
                if module_name not in tools_by_module:
                    tools_by_module[module_name] = []
                
                tools_by_module[module_name].append({
                    'function_name': function_name,
                    'category': category
                })
        
        return {
            'total_tools': len(all_tools['metadatas']),
            'tools_by_module': tools_by_module,
            'categories': vectorizer.list_all_categories()
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'total_tools': 0,
            'tools_by_module': {},
            'categories': []
        }

def main():
    """主函数"""
    print("[INFO] 检查所有工具模块的向量化情况...")
    print("=" * 60)
    
    # 初始化向量化器
    vectorizer = ToolVectorizer("tool_db")
    
    # 获取所有工具模块
    tool_modules = get_all_tool_modules()
    
    print(f"[INFO] 发现 {len(tool_modules)} 个工具模块")
    print()
    
    # 检查每个模块
    total_tools_found = 0
    total_modules_success = 0
    
    for module_name, config in tool_modules.items():
        print(f"[CHECK] 检查模块: {module_name}")
        result = check_module_tools(module_name, config)
        
        if result['import_success']:
            total_modules_success += 1
            print(f"  ✓ 导入成功")
            print(f"  ✓ 发现 {result['tools_found']} 个工具")
            total_tools_found += result['tools_found']
            
            if result['tools_list']:
                for tool in result['tools_list']:
                    print(f"    - {tool['name']} ({tool['parameters']} 参数)")
        else:
            print(f"  ✗ 导入失败: {result['error']}")
        
        print()
    
    # 检查已向量化的工具
    print("[INFO] 检查已向量化的工具...")
    vectorized_info = check_vectorized_tools(vectorizer)
    
    if 'error' not in vectorized_info:
        print(f"  ✓ 总共向量化了 {vectorized_info['total_tools']} 个工具")
        print(f"  ✓ 类别: {vectorized_info['categories']}")
        print()
        
        print("按模块分组的向量化工具:")
        for module_name, tools in vectorized_info['tools_by_module'].items():
            print(f"  {module_name}: {len(tools)} 个工具")
            for tool in tools:
                print(f"    - {tool['function_name']} ({tool['category']})")
    else:
        print(f"  ✗ 检查向量化工具失败: {vectorized_info['error']}")
    
    print()
    print("=" * 60)
    print(f"[SUMMARY] 总结:")
    print(f"  - 总模块数: {len(tool_modules)}")
    print(f"  - 成功导入模块: {total_modules_success}")
    print(f"  - 发现工具总数: {total_tools_found}")
    print(f"  - 已向量化工具: {vectorized_info.get('total_tools', 0)}")
    
    # 计算覆盖率
    if total_tools_found > 0:
        coverage = (vectorized_info.get('total_tools', 0) / total_tools_found) * 100
        print(f"  - 向量化覆盖率: {coverage:.1f}%")

if __name__ == "__main__":
    main() 