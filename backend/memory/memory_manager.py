from typing import List, Dict, Any, Optional
from .chroma_memory import ChromaMemory
import json
from datetime import datetime
from backend.config import MEMORY_DB_PATH

class MemoryManager:
    def __init__(self, persist_directory: str = MEMORY_DB_PATH):
        """
        初始化记忆管理器
        
        Args:
            persist_directory: 持久化存储目录
        """
        self.memory = ChromaMemory(persist_directory)
        
    def add_conversation_memory(self, 
                              user_id: str,
                              conversation_id: str,
                              content: str,
                              additional_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        添加对话记忆
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            content: 对话内容
            additional_metadata: 额外的元数据
            
        Returns:
            str: 存储的记忆ID
        """
        metadata = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "type": "conversation",
            "timestamp": datetime.now().isoformat()
        }
        
        if additional_metadata:
            # 过滤掉None值，因为ChromaDB不接受None作为metadata值
            filtered_metadata = {k: v for k, v in additional_metadata.items() if v is not None}
            metadata.update(filtered_metadata)
            
        return self.memory.store_memory(content, metadata)
    
    def search_memories(self,
                       query: str,
                       user_id: Optional[str] = None,
                       conversation_id: Optional[str] = None,
                       n_results: int = 3,
                       include_other_conversations: bool = True) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 搜索查询
            user_id: 用户ID（可选）
            conversation_id: 对话ID（可选）
            n_results: 返回结果数量
            include_other_conversations: 是否包含其他会话的记忆
            
        Returns:
            List[Dict]: 检索到的记忆列表
        """
        where = {}
        if user_id:
            where["user_id"] = user_id
        if conversation_id and not include_other_conversations:
            where["conversation_id"] = conversation_id
            
        return self.memory.retrieve_memories(query, n_results, where)
    
    def get_conversation_history(self,
                               conversation_id: str,
                               limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取特定对话的历史记录
        
        Args:
            conversation_id: 对话ID
            limit: 返回结果数量限制
            
        Returns:
            List[Dict]: 对话历史记录
        """
        where = {"conversation_id": conversation_id}
        return self.memory.retrieve_memories("", limit, where)
    
    def delete_conversation_memories(self, conversation_id: str) -> bool:
        """
        删除特定对话的所有记忆
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            memories = self.get_conversation_history(conversation_id)
            for memory in memories:
                self.memory.delete_memory(memory["id"])
            return True
        except Exception as e:
            print(f"Error deleting conversation memories: {e}")
            return False
    
    def update_memory(self,
                     memory_id: str,
                     content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            content: 新的内容（可选）
            metadata: 新的元数据（可选）
            
        Returns:
            bool: 是否更新成功
        """
        return self.memory.update_memory(memory_id, content, metadata) 