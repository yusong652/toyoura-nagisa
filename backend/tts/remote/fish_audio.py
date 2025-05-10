import os
from typing import List, Optional, Union
from pathlib import Path
from dotenv import load_dotenv
from fish_audio_sdk import Session, TTSRequest
from datetime import datetime
from pathlib import Path
from ..base import BaseTTS, TTSConfig, TTSException, TTSSynthesisError, TTSInitError

class FishSpeechConfig(TTSConfig):
    """Fish Speech TTS 配置类"""
    @property
    def api_key(self) -> Optional[str]:
        return self._config.get('api_key') or os.getenv('FISH_SPEECH_API_KEY')
    
    @property
    def reference_id(self) -> Optional[str]:
        return self._config.get('reference_id') or os.getenv('FISH_SPEECH_REFERENCE_ID')

class FishAudioTTS(BaseTTS):
    """Fish Speech TTS 实现类
    
    使用 Fish Speech API 进行文本到语音的转换。支持流式音频输出和文件保存。
    
    Attributes:
        session: Fish Speech API 会话对象
        model_id: 使用的模型 ID
    """
    
    def __init__(self, config: Optional[FishSpeechConfig] = None):
        """初始化 Fish Speech TTS 实例
        
        Args:
            config: Fish Speech 配置对象，可选。如果不提供，将从环境变量获取配置。
        
        Raises:
            TTSInitError: 如果缺少必要的配置（API key 或 model ID）
        """
        super().__init__(config or FishSpeechConfig())
        load_dotenv()  # 确保环境变量已加载
        
        self.api_key = self.config.api_key
        self.reference_id = self.config.reference_id
        
        if not self.api_key:
            raise TTSInitError("Fish Speech API key not found in config or environment variables")
        if not self.reference_id:
            raise TTSInitError("Fish Speech reference ID not found in config or environment variables")
        
        self.session = None
        print("FishSpeechTTS Initialized.")  # 简单打印
    
    async def initialize(self) -> bool:
        """初始化 Fish Speech 会话
        
        Returns:
            bool: 初始化是否成功
        
        Raises:
            TTSInitError: 初始化失败时抛出
        """
        try:
            self.session = Session(self.api_key)
            self._is_ready = True
            return True
        except Exception as e:
            raise TTSInitError(f"Failed to initialize Fish Speech session: {e}")
    
    async def synthesize(
        self,
        text: str,
        output_path: Optional[Union[str, Path]] = None,
        reference_id: Optional[int] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """使用 Fish Speech API 将文本转换为语音
        
        Args:
            text: 要转换的文本
            output_path: （已弃用）输出音频文件的路径，可选
            reference_id: 说话人ID，可选
            language: 语言代码，可选
            speed: 语速，默认1.0
            **kwargs: 其他参数
        
        Returns:
            bytes: 合成的音频字节流
        
        Raises:
            TTSSynthesisError: 合成过程中出现错误时抛出
        """
        if not self.is_ready:
            raise TTSSynthesisError("TTS engine not initialized. Call initialize() first.")
        try:
            # 清理文本中的颜文字和特殊符号
            cleaned_text = self.clean_text(text)
            
            tts_request = TTSRequest(
                reference_id=self.reference_id,
                text=cleaned_text
            )
            if reference_id is not None:
                tts_request.reference_id = reference_id
            audio_chunks: List[bytes] = []
            async for chunk in self.session.tts.awaitable(tts_request):
                audio_chunks.append(chunk)
            if not audio_chunks:
                print("Warning: TTS synthesis returned no audio chunks.")
                return b""
            audio_bytes = b"".join(audio_chunks)
            print(f"Synthesis complete, returning {len(audio_bytes)} bytes.")
            return audio_bytes
        except Exception as e:
            print(f"Error during Fish Speech synthesis: {e}")
            raise TTSSynthesisError(f"Error during Fish Speech synthesis: {e}")

    def save_audio_to_file(self, audio_bytes: bytes, output_path: Optional[str] = None) -> Optional[str]:
        """
        将音频字节流保存到文件。如果未指定 output_path，则自动保存到 tts/data/tts_outputs 目录下，文件名为时间戳+mp3后缀。
        Args:
            audio_bytes (bytes): 要保存的音频字节流
            output_path (Optional[str]): 输出文件路径（可选）
        Returns:
            Optional[str]: 实际保存的文件绝对路径，保存失败返回 None
        """
        try:
            if not output_path:
                output_dir = Path(__file__).parent / "data" / "tts_outputs"
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_path = output_dir / f"tts_{timestamp}.mp3"
            else:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
            return str(Path(output_path).absolute())
        except Exception as e:
            print(f"Error saving audio to file: {e}")
            return None
    
    async def shutdown(self) -> None:
        """关闭 Fish Speech 会话
        
        目前 Fish Speech SDK 似乎不需要显式关闭会话，但我们仍然重置状态
        """
        self.session = None
        self._is_ready = False
