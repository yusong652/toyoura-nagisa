"""
LLM 响应处理模型

定义LLM客户端层的响应处理逻辑和数据结构。
这些模型专门用于处理LLM的输出和响应格式转换。
"""

from typing import Union, List, Dict, Any, Optional


class LLMResponse:
    """
    简化的LLM响应类 - 专为新架构设计
    
    由于工具调用现在在LLM客户端内部处理，这个类只需要处理最终的文本响应。
    移除了所有过时的工具调用相关字段和ResponseType依赖。
    
    这是基础设施层的模型，专门处理LLM客户端的响应数据。
    """
    
    def __init__(
        self,
        content: Union[str, List[Dict[str, Any]]],
        keyword: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        初始化LLM响应对象
        
        Args:
            content: 响应内容，可以是字符串或结构化列表
            keyword: 表情关键词
            error: 错误信息（如果有）
        """
        # 确保 content 总是列表格式
        if isinstance(content, str):
            if error:
                # 错误情况下，content可能是错误信息字符串
                self.content = [{"type": "text", "text": content}]
                self.is_error = True
            else:
                self.content = [{"type": "text", "text": content}]
                self.is_error = False
        else:
            self.content = content
            self.is_error = bool(error)
        
        self.keyword = keyword
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """
        将 LLMResponse 转换为字典格式。
        
        主要用于序化和API响应。
        
        Returns:
            Dict: 响应数据的字典表示
        """
        result = {
            "content": self.content,
            "keyword": self.keyword,
        }
        if self.is_error:
            result["error"] = self.error
        return result
    
    def get_text_content(self) -> str:
        """
        提取纯文本内容
        
        Returns:
            str: 合并后的文本内容
        """
        text_parts = []
        for item in self.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "".join(text_parts)
    
    def has_error(self) -> bool:
        """
        检查是否包含错误
        
        Returns:
            bool: 是否有错误
        """
        return self.is_error