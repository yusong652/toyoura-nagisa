from abc import ABC, abstractmethod
from typing import Optional, Union, Dict, Any
from pathlib import Path
from .utils import clean_text_for_tts

class TTSException(Exception):
    """TTS 模块的基础异常类"""
    pass

class TTSInitError(TTSException):
    """TTS 初始化错误"""
    pass

class TTSSynthesisError(TTSException):
    """TTS 合成错误"""
    pass

class TTSConfig:
    """TTS 配置基类
    
    用于存储和管理 TTS 引擎的配置参数。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化配置
        
        Args:
            config: 配置字典，可选
        """
        self._config = config or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果不存在则返回默认值
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        self._config[key] = value

class BaseTTS(ABC):
    """TTS 引擎的抽象基类
    
    定义了所有 TTS 引擎必须实现的基本接口。
    """
    
    def __init__(self, config: TTSConfig):
        """初始化 TTS 引擎
        
        Args:
            config: TTS 配置对象
        """
        self.config = config
        self._is_ready = False
    
    def clean_text(self, text: str) -> str:
        """清理文本中的颜文字和特殊符号
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        return clean_text_for_tts(text)
    
    @property
    def is_ready(self) -> bool:
        """检查 TTS 引擎是否已准备就绪
        
        Returns:
            bool: 是否已准备就绪
        """
        return self._is_ready
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化 TTS 引擎
        
        Returns:
            bool: 初始化是否成功
            
        Raises:
            TTSInitError: 初始化失败时抛出
        """
        pass
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: Optional[Union[str, Path]] = None,
        reference_id: Optional[int] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
        **kwargs
    ) -> Union[bytes, str]:
        """将文本转换为语音
        
        Args:
            text: 要转换的文本
            output_path: 输出音频文件的路径，可选
            reference_id: 说话人ID，可选
            language: 语言代码，可选
            speed: 语速，默认1.0
            **kwargs: 其他参数
            
        Returns:
            Union[bytes, str]: 
                - 如果提供了output_path，返回保存的文件路径
                - 如果没有提供output_path，返回音频数据的字节串
                
        Raises:
            TTSSynthesisError: 合成过程中出现错误时抛出
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """关闭 TTS 引擎
        
        释放资源并清理状态。
        """
        pass
