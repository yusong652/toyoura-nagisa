"""
Base Local Client for Local Model Framework

Provides the foundation for local model clients with common functionality
for connection management, health checking, and service orchestration.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator
import aiohttp

from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse

logger = logging.getLogger(__name__)

class BaseLocalClient(LLMClientBase, ABC):
    """
    Abstract base class for local model clients.
    
    Provides common functionality for:
    - Service health checking
    - Connection management  
    - Error handling and retry logic
    - Service auto-start capabilities
    """
    
    def __init__(self, 
                 base_url: str,
                 service_name: str,
                 auto_start: bool = True,
                 health_endpoint: str = "/health",
                 **kwargs):
        """
        Initialize base local client.
        
        Args:
            base_url: Base URL for the local service
            service_name: Name of the service for logging
            auto_start: Whether to auto-start service if not running
            health_endpoint: Health check endpoint path
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.auto_start = auto_start
        self.health_endpoint = health_endpoint
        self.is_healthy = False
        self._health_check_interval = 30  # seconds
        
    async def ensure_service_ready(self) -> bool:
        """
        Ensure the local service is ready for requests.
        
        Returns:
            True if service is ready, False otherwise
        """
        if await self.check_health():
            return True
            
        if self.auto_start:
            logger.info(f"Attempting to start {self.service_name} service...")
            if await self.start_service():
                return await self.wait_for_service(timeout=60)
                
        return False
        
    async def check_health(self) -> bool:
        """
        Check if the service is healthy and responsive.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{self.health_endpoint}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    self.is_healthy = response.status == 200
                    return self.is_healthy
        except Exception as e:
            logger.debug(f"{self.service_name} health check failed: {e}")
            self.is_healthy = False
            return False
            
    async def wait_for_service(self, timeout: int = 60) -> bool:
        """
        Wait for service to become ready.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if service becomes ready, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if await self.check_health():
                logger.info(f"{self.service_name} service is ready!")
                return True
            await asyncio.sleep(2)
            
        logger.error(f"{self.service_name} service failed to start within {timeout}s")
        return False
        
    @abstractmethod
    async def start_service(self) -> bool:
        """
        Start the local service.
        
        Returns:
            True if service start was initiated successfully
        """
        pass
        
    @abstractmethod
    async def stop_service(self) -> bool:
        """
        Stop the local service.
        
        Returns:
            True if service was stopped successfully
        """
        pass
        
    async def generate_with_retry(self, 
                                messages: list,
                                max_retries: int = 3,
                                **kwargs) -> LLMResponse:
        """
        Generate response with automatic retry and service recovery.
        
        Args:
            messages: Input messages
            max_retries: Maximum number of retry attempts
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Ensure service is ready before each attempt
                if not await self.ensure_service_ready():
                    raise Exception(f"{self.service_name} service not available")
                    
                return await self.generate(messages, **kwargs)
                
            except Exception as e:
                last_exception = e
                logger.warning(f"{self.service_name} attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries:
                    # Mark service as unhealthy and wait before retry
                    self.is_healthy = False
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        raise last_exception or Exception(f"All {max_retries + 1} attempts failed")
        
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service status.
        
        Returns:
            Dictionary containing service information
        """
        return {
            "service_name": self.service_name,
            "base_url": self.base_url,
            "is_healthy": self.is_healthy,
            "auto_start": self.auto_start
        }