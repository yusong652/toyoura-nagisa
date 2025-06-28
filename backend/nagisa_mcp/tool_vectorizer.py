import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Callable
import inspect
import json
import hashlib
from datetime import datetime
import os
from backend.config import TOOL_DB_PATH

class ToolVectorizer:
    def __init__(self, persist_directory: str = TOOL_DB_PATH):
        """
        初始化工具向量化系统
        
        Args:
            persist_directory: 持久化存储目录
        """
        self.persist_directory = persist_directory
        # Debug: 输出持久化目录，帮助排查路径问题
        print(f"[ToolVectorizer] Using persist directory: {self.persist_directory}")
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # 创建或获取工具集合
        self.collection = self.client.get_or_create_collection(
            name="tool_functions",
            metadata={"description": "Vectorized tool functions for semantic search"}
        )
        
        # 工具注册表
        self.tool_registry = {}
    
    def _generate_tool_id(self, function_name: str, module_name: str) -> str:
        """生成工具唯一ID"""
        return hashlib.md5(f"{module_name}.{function_name}".encode()).hexdigest()
    
    def _extract_function_info(self, func: Callable, module_name: str = "") -> Dict[str, Any]:
        """提取函数信息"""
        # 获取函数签名
        sig = inspect.signature(func)
        
        # 获取函数文档
        doc = func.__doc__ or ""
        
        # 获取参数信息
        params = {}
        for name, param in sig.parameters.items():
            if name != 'self':
                params[name] = {
                    'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'required': param.default == inspect.Parameter.empty
                }
        
        return {
            'function_name': func.__name__,
            'module_name': module_name,
            'docstring': doc,
            'parameters': params,
            'return_type': str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else 'Any'
        }
    
    def _create_tool_description(self, func_info: Dict[str, Any], category: str = "", tags: List[str] = None) -> str:
        """创建工具描述文本用于向量化"""
        if tags is None:
            tags = []
        
        description_parts = [
            f"Function: {func_info['function_name']}",
            f"Category: {category}",
            f"Description: {func_info['docstring']}",
            f"Module: {func_info['module_name']}"
        ]
        
        # 添加参数信息
        if func_info['parameters']:
            param_desc = "Parameters: " + ", ".join([
                f"{name}({info['type']})" for name, info in func_info['parameters'].items()
            ])
            description_parts.append(param_desc)
        
        # 添加标签
        if tags:
            description_parts.append(f"Tags: {', '.join(tags)}")
        
        return " | ".join(description_parts)
    
    def register_tool(self, 
                     func: Callable, 
                     category: str = "",
                     tags: List[str] = None,
                     module_name: str = "",
                     metadata: Dict[str, Any] = None) -> str:
        """
        注册工具到向量数据库
        
        Args:
            func: 要注册的函数
            category: 工具类别
            tags: 标签列表
            module_name: 模块名称
            metadata: 额外元数据
            
        Returns:
            str: 工具ID
        """
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}
        
        # 提取函数信息
        func_info = self._extract_function_info(func, module_name)
        tool_id = self._generate_tool_id(func_info['function_name'], func_info['module_name'])
        
        # 创建描述文本
        description = self._create_tool_description(func_info, category, tags)
        
        # 准备元数据
        tool_metadata = {
            'function_name': func_info['function_name'],
            'module_name': func_info['module_name'],
            'category': category,
            'tags': json.dumps(list(tags)),
            'parameters': json.dumps(func_info['parameters']),
            'return_type': func_info['return_type'],
            'docstring': func_info['docstring'],
            'registered_at': datetime.now().isoformat(),
            **metadata
        }
        
        # 存储到向量数据库
        self.collection.add(
            documents=[description],
            metadatas=[tool_metadata],
            ids=[tool_id]
        )
        
        # 保存到注册表
        self.tool_registry[tool_id] = {
            'function': func,
            'info': func_info,
            'category': category,
            'tags': tags,
            'metadata': tool_metadata
        }
        
        print(f"[DEBUG] Registered tool: {func_info['function_name']} (ID: {tool_id})")
        return tool_id
    
    def search_tools(self, 
                    query: str, 
                    n_results: int = 5,
                    category_filter: Optional[str] = None,
                    tags_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        语义搜索工具
        
        Args:
            query: 搜索查询
            n_results: 返回结果数量
            category_filter: 类别过滤
            tags_filter: 标签过滤
            
        Returns:
            List[Dict]: 搜索结果
        """
        # 构建过滤条件
        where = {}
        if category_filter:
            where['category'] = category_filter
        if tags_filter:
            where['tags'] = {"$in": tags_filter}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None
        )
        
        tools = []
        for i in range(len(results["ids"][0])):
            tool_id = results["ids"][0][i]
            tool_info = {
                "id": tool_id,
                "description": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None,
                "function": self.tool_registry.get(tool_id, {}).get('function')
            }
            tools.append(tool_info)
            
        return tools
    
    def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取工具"""
        return self.tool_registry.get(tool_id)
    
    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """根据类别获取工具"""
        results = self.collection.query(
            query_texts=[""],
            n_results=100,
            where={"category": category}
        )
        
        tools = []
        for i in range(len(results["ids"][0])):
            tool_id = results["ids"][0][i]
            tool_info = {
                "id": tool_id,
                "description": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "function": self.tool_registry.get(tool_id, {}).get('function')
            }
            tools.append(tool_info)
            
        return tools
    
    def list_all_categories(self) -> List[str]:
        """列出所有工具类别"""
        results = self.collection.get()
        categories: set[str] = set()
        # ChromaDB may return metadatas as a list or list of lists depending on the API call.
        for item in results["metadatas"]:
            # Ensure we iterate over the actual metadata dicts
            if isinstance(item, list):
                iterable = item
            else:
                iterable = [item]
            for metadata in iterable:
                if metadata and metadata.get("category"):
                    categories.add(metadata["category"])
        return sorted(categories)
    
    def list_all_tags(self) -> List[str]:
        """列出所有标签"""
        results = self.collection.get()
        tags: set[str] = set()
        for item in results["metadatas"]:
            if isinstance(item, list):
                iterable = item
            else:
                iterable = [item]
            for metadata in iterable:
                if metadata and metadata.get("tags"):
                    # tags are stored as JSON strings, so ensure we parse them into a list first
                    raw_tags = metadata["tags"]
                    # Accept both list and JSON-encoded strings to be robust
                    if isinstance(raw_tags, str):
                        try:
                            raw_tags = json.loads(raw_tags)
                        except json.JSONDecodeError:
                            raw_tags = [raw_tags]
                    if isinstance(raw_tags, (list, set, tuple)):
                        tags.update(raw_tags)
        return sorted(tags)
    
    def delete_tool(self, tool_id: str) -> bool:
        """删除工具"""
        try:
            self.collection.delete(ids=[tool_id])
            if tool_id in self.tool_registry:
                del self.tool_registry[tool_id]
            return True
        except Exception as e:
            print(f"Error deleting tool: {e}")
            return False
    
    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def get_persist_directory(self) -> str:
        """Return the directory where the ChromaDB collection is persisted."""
        return self.persist_directory 