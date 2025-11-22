"""
Local LLM Client for HTTPS Communication

Simple HTTPS client for communicating with remote local LLM servers,
following the same pattern as the text-to-image tool.
"""

import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator, Union, Tuple
import httpx

from backend.domain.models.messages import BaseMessage, AssistantMessage
from backend.domain.models.response_models import LLMResponse
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.config.llm import get_llm_settings
from backend.shared.utils.text_clean import extract_response_without_think

logger = logging.getLogger(__name__)

class LocalLLMClient(LLMClientBase):
    """
    Simple local LLM client using HTTPS requests.
    
    This follows the same pattern as the text-to-image tool,
    using httpx for async HTTP communication with local LLM servers.
    """
    
    def __init__(self, 
                 server_url: str,
                 api_key: Optional[str] = None,
                 model: str = "default",
                 timeout: float = 120.0,
                 **kwargs):
        """
        Initialize local LLM client.
        
        Args:
            server_url: Base URL of the local LLM server
            api_key: Optional API key for authentication
            model: Default model name
            timeout: Request timeout in seconds
        """
        super().__init__(**kwargs)

        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

        # Initialize NoOpToolManager for local LLM (no tool support)
        from backend.infrastructure.llm.base.noop_tool_manager import NoOpToolManager
        self.tool_manager = NoOpToolManager()

        logger.info(f"Local LLM client initialized at {server_url}")
    
    async def generate(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """
        Generate response using local LLM server.
        
        Args:
            messages: Input messages
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Local LLM uses OpenAI-compatible format
            def extract_text_content(content):
                """Extract text content from message content."""
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # Extract text from list format like [{"text": "hello"}]
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    return " ".join(text_parts)
                else:
                    return str(content)
            
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": [{"role": msg.role, "content": extract_text_content(msg.content)} for msg in messages],
                "max_tokens": kwargs.get("max_tokens", 1000),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "stream": False
            }
            
            async with httpx.AsyncClient() as client:
                endpoint = f"{self.server_url}"
                
                response = await client.post(
                    endpoint,
                    headers=headers,
                    content=json.dumps(payload),
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                choice = result["choices"][0]
                
                return LLMResponse(
                    content=choice["message"]["content"]
                )
        
        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            raise
    
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        Get LLM response following the base class interface.
        
        This method wraps the generate() method to comply with the abstract base class.
        """
        try:
            # Generate response using the existing generate method
            llm_response = await self.generate(messages, **kwargs)
            
            # Clean the response content
            cleaned_content = llm_response.content
            if isinstance(cleaned_content, list):
                # Process list format content
                for item in cleaned_content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        item['text'] = extract_response_without_think(item['text'])
            elif isinstance(cleaned_content, str):
                # Process string format content and convert to structured format
                processed_text = extract_response_without_think(cleaned_content)
                cleaned_content = [{"type": "text", "text": processed_text}]

            # Create a message from the cleaned response
            final_message = AssistantMessage(role="assistant", content=cleaned_content)
            
            # Create execution metadata
            execution_metadata = {
                "provider": "local_llm",
                "model": self.model,
                "session_id": session_id
            }
            
            # Yield the final result as expected by the interface
            yield (final_message, execution_metadata)
            
        except Exception as e:
            logger.error(f"Local LLM get_response failed: {e}")
            # Yield error message
            error_message = AssistantMessage(role="assistant", content=[{"type": "text", "text": f"Error: {str(e)}"}])
            yield (error_message, {"error": str(e)})

    async def check_health(self) -> bool:
        """Check if the local LLM server is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{self.server_url}/health"
                response = await client.get(endpoint, timeout=10.0)
                return response.status_code == 200
        except Exception:
            return False

# Factory function for easy creation
def create_local_llm_client(server_url: str, **kwargs) -> LocalLLMClient:
    """Create a local LLM client."""
    return LocalLLMClient(server_url=server_url, **kwargs)

# Configuration-based client creation
def create_local_llm_client_from_config() -> Optional[LocalLLMClient]:
    """
    Create local LLM client from unified configuration.
    
    Returns:
        Configured local LLM client or None if not configured
    """
    try:
        llm_settings = get_llm_settings()
        local_llm_config = llm_settings.get_local_llm_config()
        
        if not local_llm_config.enabled:
            logger.info("Local LLM client is disabled in configuration")
            return None
        
        if not local_llm_config.server_url or local_llm_config.server_url.startswith("https://your-"):
            logger.warning("Local LLM server_url not properly configured")
            return None
        
        return LocalLLMClient(
            server_url=local_llm_config.server_url,
            api_key=local_llm_config.api_key,
            model=local_llm_config.model,
            timeout=local_llm_config.timeout
        )
    
    except Exception as e:
        logger.error(f"Failed to create local LLM client from config: {e}")
        return None

def get_local_llm_config_dict() -> Dict[str, Any]:
    """
    Get local LLM configuration as dictionary.
    
    Returns:
        Local LLM configuration dictionary
    """
    try:
        llm_settings = get_llm_settings()
        local_llm_config = llm_settings.get_local_llm_config()
        
        return {
            "enabled": local_llm_config.enabled,
            "server_url": local_llm_config.server_url,
            "api_key": local_llm_config.api_key,
            "model": local_llm_config.model,
            "timeout": local_llm_config.timeout,
            "temperature": local_llm_config.temperature,
            "top_p": local_llm_config.top_p,
            "max_tokens": local_llm_config.max_tokens
        }
    except Exception as e:
        logger.error(f"Failed to get local LLM config: {e}")
        return {"enabled": False}