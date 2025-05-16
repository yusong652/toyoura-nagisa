"""
GPT-SoVITS TTS 客户端实现
"""

import os
import httpx
import json
import base64
from typing import Optional, Union
from pathlib import Path
from backend.tts.base import BaseTTS, TTSConfig, TTSException, TTSSynthesisError, TTSInitError

class GPTSoVITSConfig(TTSConfig):
    """GPT-SoVITS TTS 配置类"""
    @property
    def server_url(self) -> str:
        url = self._config.get('server_url', 'http://localhost:9880')
        print(f"[DEBUG] GPTSoVITSConfig.server_url = {url}")
        return url
    
    @property
    def language(self) -> str:
        return self._config.get('language', 'zh')
    
    @property
    def speed(self) -> float:
        return self._config.get('speed', 1.0)

class GPTSoVITSTTS(BaseTTS):
    """GPT-SoVITS TTS 客户端实现
    
    使用 GPT-SoVITS 服务器进行文本到语音的转换。
    
    Attributes:
        client: HTTP 客户端
        config: GPT-SoVITS 配置对象
    """
    
    def __init__(self, config: Optional[GPTSoVITSConfig] = None):
        """初始化 GPT-SoVITS TTS 客户端
        
        Args:
            config: GPT-SoVITS 配置对象，可选。如果不提供，将使用默认配置。
        
        Raises:
            TTSInitError: 如果配置无效
        """
        super().__init__(config or GPTSoVITSConfig())
        self.client = httpx.AsyncClient(timeout=30.0)
        self._is_ready = False
        print("GPT-SoVITS TTS Client initialized.")
    
    async def initialize(self) -> bool:
        """初始化 GPT-SoVITS 客户端
        
        Returns:
            bool: 初始化是否成功
        """
        self._is_ready = True
        return True
    
    async def synthesize(
        self,
        text: str,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> bytes:
        if not self.is_ready:
            raise TTSSynthesisError("TTS client not initialized. Call initialize() first.")
        try:
            cleaned_text = self.clean_text(text)
            data = dict(self.config._config)
            data.update(kwargs)
            data["text"] = cleaned_text
            response = await self.client.post(
                f"{self.config.server_url}",
                json=data
            )
            if response.status_code != 200:
                raise TTSSynthesisError(f"GPT-SoVITS server returned error: {response.text}")
            audio_bytes = response.content
            if not audio_bytes:
                raise TTSSynthesisError("No audio data in response")
            if output_path:
                self.save_audio_to_file(audio_bytes, output_path, audio_format="wav")
            return audio_bytes
        except Exception as e:
            print(f"Error during GPT-SoVITS synthesis: {e}")
            raise TTSSynthesisError(f"Error during GPT-SoVITS synthesis: {e}")
    
    async def shutdown(self) -> None:
        """关闭 GPT-SoVITS 客户端"""
        await self.client.aclose()
        self._is_ready = False
