"""
Ollama Client for Lightweight Local Inference

Provides integration with Ollama for easy-to-use local model serving,
particularly suitable for ASR, embedding, and lightweight inference tasks.
"""

import asyncio
import json
import logging
import subprocess
from typing import List, Dict, Any, Optional, AsyncGenerator
import ollama

from backend.chat.models import BaseMessage, LLMResponse
from .base_local_client import BaseLocalClient

logger = logging.getLogger(__name__)

class OllamaClient(BaseLocalClient):
    """
    Ollama client for lightweight local inference.
    
    Features:
    - Easy model management and downloading
    - GGUF quantized model support
    - CPU and GPU inference
    - Built-in embedding generation
    - ASR model support (Whisper)
    """
    
    def __init__(self,
                 model_name: str = "llama3.2:3b",
                 base_url: str = "http://localhost:11434",
                 **kwargs):
        """
        Initialize Ollama client.
        
        Args:
            model_name: Ollama model name (e.g., "llama3.2:3b", "whisper:large")
            base_url: Ollama server base URL
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(
            base_url=base_url,
            service_name="Ollama",
            health_endpoint="/api/tags",
            **kwargs
        )
        
        self.model_name = model_name
        self.ollama_client = ollama.Client(host=base_url)
        self._server_process = None
        
    async def start_service(self) -> bool:
        """
        Start the Ollama server.
        
        Returns:
            True if server start was initiated successfully
        """
        try:
            # Check if Ollama is already running
            if await self.check_health():
                logger.info("Ollama server is already running")
                return True
                
            # Extract host and port from base_url
            host = "0.0.0.0"
            port = self.base_url.split(":")[-1]
            
            cmd = ["ollama", "serve"]
            env = {
                "OLLAMA_HOST": f"{host}:{port}",
                "OLLAMA_ORIGINS": "*"
            }
            
            logger.info(f"Starting Ollama server on {host}:{port}")
            
            self._server_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for server to start
            await asyncio.sleep(3)
            
            # Ensure model is available
            await self.ensure_model_available()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Ollama server: {e}")
            return False
            
    async def stop_service(self) -> bool:
        """
        Stop the Ollama server.
        
        Returns:
            True if server was stopped successfully
        """
        if self._server_process:
            try:
                self._server_process.terminate()
                await asyncio.sleep(3)
                
                if self._server_process.poll() is None:
                    self._server_process.kill()
                    
                self._server_process = None
                logger.info("Ollama server stopped")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop Ollama server: {e}")
                return False
                
        return True
        
    async def ensure_model_available(self) -> bool:
        """
        Ensure the specified model is available locally.
        
        Returns:
            True if model is available or was downloaded successfully
        """
        try:
            # Check if model exists
            models = await self.get_models()
            if self.model_name in models:
                logger.info(f"Model {self.model_name} is already available")
                return True
                
            # Download model if not available
            logger.info(f"Downloading model {self.model_name}...")
            
            # Use subprocess to run ollama pull command
            process = subprocess.Popen(
                ["ollama", "pull", self.model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Model {self.model_name} downloaded successfully")
                return True
            else:
                logger.error(f"Failed to download model {self.model_name}: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error ensuring model availability: {e}")
            return False
            
    async def generate(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """
        Generate response using Ollama.
        
        Args:
            messages: Input messages
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
        """
        try:
            # Convert messages to Ollama format
            ollama_messages = self._convert_messages_to_ollama(messages)
            
            # Extract generation parameters
            model = kwargs.get('model', self.model_name)
            stream = kwargs.get('stream', False)
            options = {
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
                'top_k': kwargs.get('top_k', 40),
                'num_predict': kwargs.get('max_tokens', 1000)
            }
            
            if stream:
                return await self._generate_stream(ollama_messages, model, options, **kwargs)
            else:
                return await self._generate_sync(ollama_messages, model, options, **kwargs)
                
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
            
    async def _generate_sync(self, 
                           messages: List[Dict],
                           model: str,
                           options: Dict,
                           **kwargs) -> LLMResponse:
        """Generate synchronous response."""
        response = self.ollama_client.chat(
            model=model,
            messages=messages,
            options=options,
            stream=False
        )
        
        content = response['message']['content']
        
        return LLMResponse(
            content=content,
            finish_reason=response.get('done_reason', 'stop'),
            usage={
                "prompt_tokens": response.get('prompt_eval_count', 0),
                "completion_tokens": response.get('eval_count', 0),
                "total_tokens": response.get('prompt_eval_count', 0) + response.get('eval_count', 0)
            },
            model=model,
            provider="ollama"
        )
        
    async def _generate_stream(self, 
                             messages: List[Dict],
                             model: str,
                             options: Dict,
                             **kwargs) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        stream = self.ollama_client.chat(
            model=model,
            messages=messages,
            options=options,
            stream=True
        )
        
        for chunk in stream:
            if 'message' in chunk and 'content' in chunk['message']:
                yield chunk['message']['content']
                
    def _convert_messages_to_ollama(self, messages: List[BaseMessage]) -> List[Dict]:
        """Convert internal message format to Ollama format."""
        ollama_messages = []
        
        for msg in messages:
            ollama_msg = {
                "role": msg.role,
                "content": msg.content
            }
            
            ollama_messages.append(ollama_msg)
            
        return ollama_messages
        
    async def get_models(self) -> List[str]:
        """
        Get list of available models.
        
        Returns:
            List of model names
        """
        try:
            models_response = self.ollama_client.list()
            return [model['name'] for model in models_response['models']]
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []
            
    async def generate_embeddings(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Input text
            model: Embedding model name
            
        Returns:
            List of embedding values
        """
        try:
            response = self.ollama_client.embeddings(
                model=model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return []
            
    async def transcribe_audio(self, audio_path: str, model: str = "whisper:large") -> str:
        """
        Transcribe audio using Whisper model.
        
        Args:
            audio_path: Path to audio file
            model: Whisper model name
            
        Returns:
            Transcribed text
        """
        try:
            with open(audio_path, 'rb') as audio_file:
                response = self.ollama_client.generate(
                    model=model,
                    prompt="Transcribe this audio:",
                    images=[audio_file.read()]
                )
                return response['response']
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return ""
            
    async def delete_model(self, model_name: str) -> bool:
        """
        Delete a model from local storage.
        
        Args:
            model_name: Name of model to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            self.ollama_client.delete(model_name)
            logger.info(f"Model {model_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return False
            
    def get_service_info(self) -> Dict[str, Any]:
        """Get detailed service information."""
        info = super().get_service_info()
        info.update({
            "model_name": self.model_name,
            "server_running": self._server_process is not None and self._server_process.poll() is None
        })
        return info