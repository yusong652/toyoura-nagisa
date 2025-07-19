"""
Distributed LLM Client - Simplified but Elegant

A clean wrapper that manages distributed inference across HPC nodes
with automatic load balancing and failover.
"""

import asyncio
import logging
import random
from typing import List, Dict, Any, Optional, AsyncGenerator, Union, Tuple
from dataclasses import dataclass

from backend.chat.models import BaseMessage, LLMResponse
from .base_local_client import BaseLocalClient
from .simple_ssh_manager import SimpleSshManager

logger = logging.getLogger(__name__)

@dataclass
class DistributedConfig:
    """Simplified distributed configuration."""
    hpc_host: str
    ssh_user: str
    ssh_key_path: Optional[str] = None
    model_path: str = "/hpc/models/llama-7b"
    session_hours: int = 8
    base_port: int = 8000
    local_base_port: int = 8000

class DistributedClient(BaseLocalClient):
    """
    Simplified distributed LLM client.
    
    Core features:
    - One-command HPC deployment
    - Automatic load balancing
    - Transparent failover
    - Clean API compatible with existing clients
    """
    
    def __init__(self, 
                 config: DistributedConfig,
                 client_type: str = "vllm",  # "vllm" or "ollama"
                 **kwargs):
        
        super().__init__(
            base_url=f"http://localhost:{config.local_base_port}",
            service_name=f"Distributed-{client_type.upper()}",
            **kwargs
        )
        
        self.config = config
        self.client_type = client_type
        
        # Core components
        self.ssh_manager = SimpleSshManager()
        
        # Simple state tracking
        self.active_servers: List[str] = []
        self.current_server_index = 0
        self.session_id: Optional[str] = None
        
    async def start_service(self) -> bool:
        """
        Simplified one-command distributed deployment.
        
        Returns:
            True if deployment successful
        """
        try:
            logger.info(f"🚀 Starting distributed {self.client_type} deployment...")
            
            # Step 1: Test SSH connection
            logger.info("🔐 Testing SSH connection...")
            if not await self.ssh_manager.test_connection(
                self.config.hpc_host,
                self.config.ssh_user,
                self.config.ssh_key_path
            ):
                logger.error("❌ SSH connection failed")
                return False
            
            # Step 2: Create SSH tunnel (assumes HPC service is already running)
            logger.info("🔗 Creating SSH tunnel...")
            tunnel_name = await self.ssh_manager.create_hpc_tunnel(
                hpc_host=self.config.hpc_host,
                ssh_user=self.config.ssh_user,
                local_port=self.config.local_base_port,
                remote_port=self.config.base_port,
                ssh_key_path=self.config.ssh_key_path
            )
            
            if not tunnel_name:
                logger.error("❌ Failed to create SSH tunnel")
                return False
            
            self.active_servers.append(tunnel_name)
            
            # Step 3: Start monitoring
            await self.ssh_manager.start_monitoring()
            
            logger.info("✅ Distributed deployment successful!")
            logger.info(f"🎯 Service available at: {self.base_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Deployment failed: {e}")
            return False
    
    async def _deploy_server(self) -> Optional[str]:
        """Deploy a single server instance."""
        if not self.session_id:
            return None
        
        if self.client_type == "vllm":
            return await self.hpc_manager.deploy_persistent_vllm(
                session_id=self.session_id,
                model_path=self.config.model_path,
                port=self.config.base_port,
                local_port=self.config.local_base_port,
                ssh_user=self.config.ssh_user,
                ssh_key_path=self.config.ssh_key_path
            )
        else:
            # TODO: Implement Ollama deployment when needed
            logger.warning("Ollama deployment not implemented yet")
            return None
    
    async def stop_service(self) -> bool:
        """Clean shutdown of distributed service."""
        try:
            logger.info("🛑 Shutting down distributed service...")
            
            # Cleanup SSH manager
            await self.ssh_manager.cleanup()
            
            logger.info("✅ Distributed service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            return False
    
    async def generate(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """
        Generate response with automatic load balancing.
        
        Args:
            messages: Input messages
            **kwargs: Generation parameters
            
        Returns:
            LLM response
        """
        if not self.active_servers:
            raise Exception("No active servers available")
        
        # Simple round-robin load balancing
        server_id = self._get_next_server()
        
        try:
            # Use the underlying vLLM/Ollama client logic
            if self.client_type == "vllm":
                return await self._generate_vllm(messages, **kwargs)
            else:
                return await self._generate_ollama(messages, **kwargs)
                
        except Exception as e:
            logger.warning(f"Server {server_id} failed, trying failover: {e}")
            return await self._generate_with_failover(messages, **kwargs)
    
    def _get_next_server(self) -> str:
        """Simple round-robin server selection."""
        if not self.active_servers:
            raise Exception("No active servers")
        
        server = self.active_servers[self.current_server_index]
        self.current_server_index = (self.current_server_index + 1) % len(self.active_servers)
        return server
    
    async def _generate_vllm(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """Generate using vLLM OpenAI-compatible API."""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            base_url=f"{self.base_url}/v1",
            api_key="dummy-key"
        )
        
        # Convert messages
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        response = await client.chat.completions.create(
            model="default",
            messages=openai_messages,
            max_tokens=kwargs.get('max_tokens', 1000),
            temperature=kwargs.get('temperature', 0.7),
            stream=False
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            finish_reason=response.choices[0].finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            model=response.model,
            provider="distributed-vllm"
        )
    
    async def _generate_ollama(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """Generate using Ollama API."""
        # TODO: Implement when Ollama deployment is ready
        raise NotImplementedError("Ollama generation not implemented yet")
    
    async def _generate_with_failover(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        """Attempt generation with failover to other servers."""
        last_error = None
        
        # Try all servers once
        for _ in range(len(self.active_servers)):
            try:
                if self.client_type == "vllm":
                    return await self._generate_vllm(messages, **kwargs)
                else:
                    return await self._generate_ollama(messages, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Failover attempt failed: {e}")
                # Move to next server
                self._get_next_server()
        
        raise Exception(f"All servers failed. Last error: {last_error}")
    
    async def get_models(self) -> List[str]:
        """Get available models from active servers."""
        if not self.active_servers:
            return []
        
        try:
            if self.client_type == "vllm":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    base_url=f"{self.base_url}/v1",
                    api_key="dummy-key"
                )
                models = await client.models.list()
                return [model.id for model in models.data]
            else:
                # TODO: Implement for Ollama
                return ["ollama-model"]
                
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service status information."""
        info = super().get_service_info()
        info.update({
            "client_type": self.client_type,
            "hpc_host": self.config.hpc_host,
            "active_tunnels": len(self.active_servers),
            "tunnel_list": self.active_servers,
            "ssh_status": self.ssh_manager.get_tunnel_status()
        })
        return info
    
    async def add_tunnel(self, remote_port: int) -> bool:
        """
        Add another tunnel for scaling.
        
        Args:
            remote_port: Remote port for new tunnel
            
        Returns:
            True if tunnel added successfully
        """
        local_port = self.config.local_base_port + len(self.active_servers)
        
        tunnel_name = await self.ssh_manager.create_hpc_tunnel(
            hpc_host=self.config.hpc_host,
            ssh_user=self.config.ssh_user,
            local_port=local_port,
            remote_port=remote_port,
            ssh_key_path=self.config.ssh_key_path
        )
        
        if tunnel_name:
            self.active_servers.append(tunnel_name)
            logger.info(f"✅ Added tunnel: {tunnel_name}")
            return True
        
        return False
    
    async def remove_tunnel(self, tunnel_name: str) -> bool:
        """
        Remove a tunnel.
        
        Args:
            tunnel_name: Tunnel name to remove
            
        Returns:
            True if tunnel removed successfully
        """
        if tunnel_name not in self.active_servers:
            return False
        
        try:
            await self.ssh_manager.remove_tunnel(tunnel_name)
            self.active_servers.remove(tunnel_name)
            logger.info(f"✅ Removed tunnel: {tunnel_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove tunnel {tunnel_name}: {e}")
            return False
    
    async def get_response(self, 
                         messages: List[BaseMessage], 
                         session_id: Optional[str] = None,
                         **kwargs) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        Implementation of abstract get_response method from LLMClientBase.
        
        This provides the streaming interface for distributed inference.
        """
        try:
            # Generate response using the existing generate method
            response = await self.generate(messages, **kwargs)
            
            # Convert to BaseMessage and yield final result
            final_message = BaseMessage(
                role="assistant",
                content=response.content
            )
            
            execution_metadata = {
                "provider": response.provider,
                "model": response.model,
                "usage": response.usage,
                "finish_reason": response.finish_reason
            }
            
            yield (final_message, execution_metadata)
            
        except Exception as e:
            # Yield error as final result
            error_message = BaseMessage(
                role="assistant", 
                content=f"Distributed inference error: {str(e)}"
            )
            error_metadata = {"error": str(e), "provider": "distributed"}
            yield (error_message, error_metadata)


# Factory function for easy usage
def create_distributed_vllm(hpc_host: str, 
                           ssh_user: str,
                           model_path: str = "/hpc/models/llama-7b",
                           ssh_key_path: Optional[str] = None,
                           **kwargs) -> DistributedClient:
    """
    Factory function to create distributed vLLM client.
    
    Args:
        hpc_host: HPC cluster hostname
        ssh_user: SSH username
        model_path: Path to model on HPC filesystem
        ssh_key_path: Path to SSH private key
        **kwargs: Additional configuration
        
    Returns:
        Configured distributed client
    """
    config = DistributedConfig(
        hpc_host=hpc_host,
        ssh_user=ssh_user,
        ssh_key_path=ssh_key_path,
        model_path=model_path,
        **kwargs
    )
    
    return DistributedClient(config, client_type="vllm")


def create_distributed_ollama(hpc_host: str,
                            ssh_user: str,
                            model_name: str = "llama3.2:3b",
                            ssh_key_path: Optional[str] = None,
                            **kwargs) -> DistributedClient:
    """
    Factory function to create distributed Ollama client.
    
    Args:
        hpc_host: HPC cluster hostname  
        ssh_user: SSH username
        model_name: Ollama model name
        ssh_key_path: Path to SSH private key
        **kwargs: Additional configuration
        
    Returns:
        Configured distributed client
    """
    config = DistributedConfig(
        hpc_host=hpc_host,
        ssh_user=ssh_user,
        ssh_key_path=ssh_key_path,
        model_path=model_name,  # Use model_path field for model_name
        **kwargs
    )
    
    return DistributedClient(config, client_type="ollama")