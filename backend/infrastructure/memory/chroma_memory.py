import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import os
import json
from datetime import datetime
from backend.config import MEMORY_DB_PATH

class ChromaMemory:
    def __init__(self, persist_directory: str = MEMORY_DB_PATH):
        """
        初始化ChromaDB记忆系统
        
        Args:
            persist_directory: 持久化存储目录
        """
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # 创建或获取记忆集合
        self.collection = self.client.get_or_create_collection(
            name="conversation_memory",
            metadata={"description": "Long-term conversation memory storage"}
        )
    
    def store_memory(self, 
                    content: str, 
                    metadata: Optional[Dict[str, Any]] = None,
                    timestamp: Optional[str] = None) -> str:
        """
        存储新的记忆
        
        Args:
            content: 记忆内容
            metadata: 元数据
            timestamp: 时间戳（可选，默认使用当前时间）
            
        Returns:
            str: 存储的记忆ID
        """
        if metadata is None:
            metadata = {}
        else:
            # 过滤掉None值，因为ChromaDB不接受None作为metadata值
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
        if timestamp is None:
            timestamp = datetime.now().isoformat()
            
        metadata["timestamp"] = timestamp
        
        # 生成唯一ID
        memory_id = f"memory_{timestamp}"
        
        # 存储记忆
        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[memory_id]
        )
        
        return memory_id
    
    def retrieve_memories(self, 
                         query: str, 
                         n_results: int = 5,
                         where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        检索相关记忆
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            where: 过滤条件
            
        Returns:
            List[Dict]: 检索到的记忆列表
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where
        )
        
        memories = []
        for i in range(len(results["ids"][0])):
            memory = {
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            }
            memories.append(memory)
            
        return memories
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除指定记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False
    
    def update_memory(self, 
                     memory_id: str, 
                     content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新现有记忆
        
        Args:
            memory_id: 记忆ID
            content: 新的内容（可选）
            metadata: 新的元数据（可选）
            
        Returns:
            bool: 是否更新成功
        """
        try:
            if content is not None:
                self.collection.update(
                    ids=[memory_id],
                    documents=[content]
                )
            
            if metadata is not None:
                # 过滤掉None值，因为ChromaDB不接受None作为metadata值
                filtered_metadata = {k: v for k, v in metadata.items() if v is not None}
                if filtered_metadata:  # 只在有有效metadata时才更新
                    self.collection.update(
                        ids=[memory_id],
                        metadatas=[filtered_metadata]
                    )
                
            return True
        except Exception as e:
            print(f"Error updating memory: {e}")
            return False 