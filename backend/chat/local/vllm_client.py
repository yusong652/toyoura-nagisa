"""
vLLM Client for High-Performance Local Inference

Provides integration with vLLM inference server for high-performance
local model serving with OpenAI-compatible API.
"""

import asyncio
import json
import logging
import subprocess
from typing import List, Dict, Any, Optional, AsyncGenerator
import aiohttp
from openai import AsyncOpenAI

from backend.chat.models import BaseMessage, LLMResponse
from .base_local_client import BaseLocalClient

logger = logging.getLogger(__name__)

class VLLMClient(BaseLocalClient):
    """
    vLLM client for high-performance local inference.
    
    Features:
    - OpenAI-compatible API interface
    - High-performance GPU acceleration
    - Batch processing optimization
    - Model hot-swapping support
    """
    
    def __init__(self,
                 model_path: str,
                 base_url: str = "http://localhost:8000",
                 gpu_memory_utilization: float = 0.9,
                 max_model_len: Optional[int] = None,
                 tensor_parallel_size: int = 1,
                 **kwargs):
        """
        Initialize vLLM client.
        
        Args:
            model_path: Path to the model (local path or HuggingFace model ID)
            base_url: vLLM server base URL
            gpu_memory_utilization: GPU memory utilization ratio
            max_model_len: Maximum model sequence length
            tensor_parallel_size: Number of GPUs for tensor parallelism
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(
            base_url=base_url,
            service_name="vLLM",
            health_endpoint="/health",
            **kwargs
        )
        
        self.model_path = model_path
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len
        self.tensor_parallel_size = tensor_parallel_size
        
        # OpenAI client for vLLM
        self.openai_client = AsyncOpenAI(
            base_url=f"{self.base_url}/v1",
            api_key="dummy-key"  # vLLM doesn't require real API key
        )
        
        self._server_process = None
        
    async def start_service(self) -> bool:
        """
        Start the vLLM inference server.
        
        Returns:
            True if server start was initiated successfully
        """
        if self._server_process and self._server_process.poll() is None:
            logger.info("vLLM server is already running")
            return True
            
        try:
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", self.model_path,
                "--host", "0.0.0.0",
                "--port", str(self.base_url.split(":")[-1]),
                "--gpu-memory-utilization", str(self.gpu_memory_utilization),
                "--tensor-parallel-size", str(self.tensor_parallel_size)
            ]
            
            if self.max_model_len:
                cmd.extend(["--max-model-len", str(self.max_model_len)])
                
            logger.info(f"Starting vLLM server: {' '.join(cmd)}")
            
            self._server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start vLLM server: {e}")
            return False
            
    async def stop_service(self) -> bool:
        """
        Stop the vLLM inference server.
        
        Returns:
            True if server was stopped successfully
        """
        if self._server_process:
            try:
                self._server_process.terminate()
                await asyncio.sleep(5)
                
                if self._server_process.poll() is None:
                    self._server_process.kill()
                    
                self._server_process = None
                logger.info("vLLM server stopped")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop vLLM server: {e}")
                return False
                
        return True
        
    async def generate(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """
        Generate response using vLLM.
        
        Args:
            messages: Input messages
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
        """
        try:
            # Convert messages to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            # Extract generation parameters
            model = kwargs.get('model', 'default')
            max_tokens = kwargs.get('max_tokens', 1000)
            temperature = kwargs.get('temperature', 0.7)
            top_p = kwargs.get('top_p', 0.9)
            stream = kwargs.get('stream', False)
            
            if stream:
                return await self._generate_stream(
                    openai_messages, model, max_tokens, temperature, top_p, **kwargs
                )
            else:
                return await self._generate_sync(
                    openai_messages, model, max_tokens, temperature, top_p, **kwargs
                )
                
        except Exception as e:
            logger.error(f"vLLM generation failed: {e}")
            raise
            
    async def _generate_sync(self, 
                           messages: List[Dict],
                           model: str,
                           max_tokens: int,
                           temperature: float,
                           top_p: float,
                           **kwargs) -> LLMResponse:
        """Generate synchronous response."""
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=False
        )
        
        content = response.choices[0].message.content
        
        return LLMResponse(
            content=content,
            finish_reason=response.choices[0].finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            model=response.model,
            provider="vllm"
        )
        
    async def _generate_stream(self, 
                             messages: List[Dict],
                             model: str,
                             max_tokens: int,
                             temperature: float,
                             top_p: float,
                             **kwargs) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        stream = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    def _convert_messages_to_openai(self, messages: List[BaseMessage]) -> List[Dict]:
        """Convert internal message format to OpenAI format."""
        openai_messages = []
        
        for msg in messages:
            openai_msg = {
                "role": msg.role,
                "content": msg.content
            }
            
            # Handle additional fields if present
            if hasattr(msg, 'name') and msg.name:
                openai_msg["name"] = msg.name
                
            openai_messages.append(openai_msg)
            
        return openai_messages
        
    async def get_models(self) -> List[str]:
        """
        Get list of available models.
        
        Returns:
            List of model names
        """
        try:
            models = await self.openai_client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []
            
    async def get_server_stats(self) -> Dict[str, Any]:
        """
        Get vLLM server statistics.
        
        Returns:
            Dictionary containing server stats
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/stats") as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        except Exception as e:
            logger.error(f"Failed to get server stats: {e}")
            return {}
            
    def get_service_info(self) -> Dict[str, Any]:
        """Get detailed service information."""
        info = super().get_service_info()
        info.update({
            "model_path": self.model_path,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_model_len": self.max_model_len,
            "tensor_parallel_size": self.tensor_parallel_size,
            "server_running": self._server_process is not None and self._server_process.poll() is None
        })
        return info