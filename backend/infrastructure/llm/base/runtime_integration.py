"""
Runtime Integration - Seamless integration with existing LLM client

This module shows how to integrate runtime context management with the
existing LLM client infrastructure without breaking changes.
"""

from typing import Optional, Dict, Any
from backend.infrastructure.llm.base.client import LLMClientBase


class RuntimeContextIntegration:
    """
    Integration helper for adding runtime context to existing LLM clients.
    
    This class provides static methods to enhance existing LLM clients
    with runtime tool context preservation capabilities.
    """
    
    @staticmethod
    def enhance_client_get_response(original_client: LLMClientBase):
        """
        Monkey-patch existing client to use runtime context.
        
        This is a non-invasive way to add runtime capabilities
        to existing clients without modifying their code.
        
        Args:
            original_client: Existing LLM client instance
        """
        # Store original method
        original_get_response = original_client.get_response
        
        async def enhanced_get_response(messages, session_id=None, **kwargs):
            """Enhanced get_response with runtime context."""
            
            # Create runtime-enhanced context manager if session_id provided
            if session_id:
                # Import here to avoid circular dependency
                from backend.infrastructure.llm.providers.gemini.runtime_context_manager import GeminiRuntimeContextManager
                from backend.infrastructure.llm.providers.anthropic.runtime_context_manager import AnthropicRuntimeContextManager
                from backend.infrastructure.llm.providers.openai.runtime_context_manager import OpenAIRuntimeContextManager
                
                # Map provider to runtime context manager
                runtime_managers = {
                    'GeminiClient': GeminiRuntimeContextManager,
                    'AnthropicClient': AnthropicRuntimeContextManager,
                    'OpenAIClient': OpenAIRuntimeContextManager,
                }
                
                client_class = original_client.__class__.__name__
                if client_class in runtime_managers:
                    # Use runtime-enhanced context manager
                    context_manager = runtime_managers[client_class](session_id)
                    
                    # Replace context manager creation in the flow
                    original_client._runtime_context_manager = context_manager
                    
                    # Temporarily override _get_context_manager
                    original_get_context = original_client._get_context_manager
                    original_client._get_context_manager = lambda: context_manager
                    
                    try:
                        # Call original with enhanced context
                        async for item in original_get_response(messages, session_id, **kwargs):
                            yield item
                    finally:
                        # Restore original method
                        original_client._get_context_manager = original_get_context
                else:
                    # Fallback to original for unsupported providers
                    async for item in original_get_response(messages, session_id, **kwargs):
                        yield item
            else:
                # No session_id, use original flow
                async for item in original_get_response(messages, session_id, **kwargs):
                    yield item
        
        # Replace method
        original_client.get_response = enhanced_get_response
        return original_client


# Example usage showing integration with minimal changes
def example_integration():
    """
    Example showing how to integrate runtime context with minimal code changes.
    
    This demonstrates the integration pattern that can be applied
    in the existing codebase with minimal disruption.
    """
    
    # Existing code - unchanged
    from backend.infrastructure.llm.providers.gemini.client import GeminiClient
    
    # Create client as normal
    client = GeminiClient(tools_enabled=True)
    
    # ADD THIS LINE: Enhance with runtime capabilities
    RuntimeContextIntegration.enhance_client_get_response(client)
    
    # Use client as normal - runtime context automatically managed
    async def use_client():
        messages = [...]  # Your messages
        
        # Session ID enables runtime context
        async for response in client.get_response(messages, session_id="abc123"):
            # Tool context automatically preserved during session
            process_response(response)
    
    # Runtime context automatically cleaned on session end
    from backend.infrastructure.llm.base.runtime_context_manager import RuntimeContextManager
    RuntimeContextManager.clear_session_context("abc123")


def integrate_at_session_level():
    """
    Alternative: Integrate at session management level.
    
    This shows how to integrate runtime context management
    at the session/connection level for cleaner architecture.
    """
    
    class SessionWithRuntimeContext:
        """Enhanced session with automatic runtime context management."""
        
        def __init__(self, session_id: str, provider: str):
            self.session_id = session_id
            self.provider = provider
            
            # Initialize runtime context for session
            from backend.infrastructure.llm.base.runtime_context_manager import RuntimeContextManager
            self.runtime_context = RuntimeContextManager.get_or_create_context(
                session_id, provider
            )
        
        async def process_message(self, client: LLMClientBase, messages):
            """Process message with runtime context."""
            
            # Enhance client for this session
            RuntimeContextIntegration.enhance_client_get_response(client)
            
            # Process with runtime context
            async for response in client.get_response(messages, self.session_id):
                yield response
        
        def cleanup(self):
            """Clean up runtime context on session end."""
            from backend.infrastructure.llm.base.runtime_context_manager import RuntimeContextManager
            RuntimeContextManager.clear_session_context(self.session_id)
    
    # Usage
    session = SessionWithRuntimeContext("session123", "gemini")
    # ... use session ...
    session.cleanup()  # Cleans runtime context