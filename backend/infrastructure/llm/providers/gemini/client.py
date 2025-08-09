"""
Gemini client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Gemini-specific functionality.
"""

from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union

from google import genai
from google.genai import types

from backend.config import get_llm_settings, get_system_prompt
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage

# Import Gemini-specific implementations
from .config import get_gemini_client_config
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .response_processor import GeminiResponseProcessor
from .tool_manager import GeminiToolManager
from .content_generators import GeminiTitleGenerator, GeminiImagePromptGenerator, GeminiWebSearchGenerator


class GeminiClient(LLMClientBase):
    """
    Enhanced Google Gemini client with unified architecture.
    
    Key Features:
    - Inherits from unified LLMClientBase
    - Uses shared components where possible
    - Implements Gemini-specific functionality
    - Original response preservation during tool calling sequences
    - Thinking chain and validation field integrity
    - Real-time streaming tool call notifications
    - Comprehensive tool management and execution
    - Modular component architecture
    
    Components:
    - GeminiContextManager: Manages context and state for Gemini API calls
    - GeminiDebugger: Provides detailed request/response logging in debug mode
    - GeminiResponseProcessor: Enhanced response processing with tool call extraction
    - GeminiToolManager: Advanced MCP tool integration
    - Content Generators: Specialized content generation utilities
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize enhanced Gemini client with context preservation capabilities.
        
        Args:
            api_key: Google API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.client = genai.Client(api_key=api_key)
        
        # Initialize Gemini-specific configuration
        config_overrides = {}
        
        # Extract relevant configuration from extra_config for overrides
        if 'model' in self.extra_config:
            config_overrides['model_settings'] = {'model': self.extra_config['model']}
        if 'temperature' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['temperature'] = self.extra_config['temperature']
        if 'max_output_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['max_output_tokens'] = self.extra_config['max_output_tokens']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.gemini_config = get_gemini_client_config(**config_overrides)
        
        print(f"Enhanced Gemini Client initialized with model: {self.gemini_config.model_settings.model}")

        # Initialize component managers with unified architecture
        self.tool_manager = GeminiToolManager(tools_enabled=self.tools_enabled)

    # ========== CORE STREAMING INTERFACE ==========

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        Streaming LLM response processor with real-time notifications.
        
        Streaming processor designed for real-time tool calling notifications using event-driven pattern:
        1. Real-time yield tool call start/progress/completion notifications
        2. Maintain complete execution tracking and error handling
        3. Final return of complete response and metadata
        4. Fully compatible with existing architecture
        
        Args:
            messages: Input message history
            session_id: Session ID for tool and context management
            **kwargs: Additional API configuration parameters
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Intermediate notifications: tool calling status updates
            - Final result: (final_message, execution_metadata)
        """
        # === INITIALIZATION PHASE ===
        execution_id = self._generate_execution_id()
        debug = self.gemini_config.debug

        # Create independent context manager - ensure state isolation
        context_manager = GeminiContextManager()
        context_manager.initialize_from_messages(messages)
        
        # Execution metadata - complete tracking
        metadata = {
            'execution_id': execution_id,
            'session_id': session_id,
            'start_time': self._get_timestamp(),
            'end_time': None,
            'iterations': 0,
            'api_calls': 0,
            'tool_calls_executed': 0,
            'thinking_preserved': False,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE - Streaming tool calling loop ===
            # Get max tool calling iterations from configuration
            max_iterations = get_llm_settings().max_tool_iterations
            
            final_response = None
            async for item in self._streaming_tool_calling_loop(
                context_manager, session_id, max_iterations, metadata, debug, **kwargs
            ):
                if isinstance(item, dict):
                    # Intermediate notification - yield directly to API layer
                    yield item
                else:
                    # Final response - save for subsequent processing
                    final_response = item
            
            # === FINALIZATION PHASE ===
            metadata['status'] = 'completed'
            metadata['end_time'] = self._get_timestamp()
            
            # Extract thinking content
            thinking_content = GeminiResponseProcessor.extract_thinking_content(final_response)
            metadata['thinking_preserved'] = thinking_content is not None
            
            # Extract keyword - extract from original response before formatting
            original_text = GeminiResponseProcessor.extract_text_content(final_response)
            from backend.shared.utils.text_parser import parse_llm_output
            _, extracted_keyword = parse_llm_output(original_text)
            metadata['keyword'] = extracted_keyword
            
            # Send tool use concluded notification if tools were used
            if metadata['tool_calls_executed'] > 0:
                yield {
                    'type': 'NAGISA_TOOL_USE_CONCLUDED',
                    'execution_id': execution_id
                }
            
            # Create final storage message - use ResponseProcessor instead of context_manager
            final_message = GeminiResponseProcessor.format_response_for_storage(final_response)
            
            # Yield final result
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            
            # Yield error notification
            yield {
                'type': 'error',
                'error': f"Tool calling sequence {execution_id} failed: {e}"
            }
            
            raise Exception(f"Tool calling sequence {execution_id} failed: {e}")

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    async def get_function_call_schemas(self, session_id: str) -> List[types.Tool]:
        """
        Get all MCP tool schemas in Gemini format.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[types.Tool]: Tool schemas in Gemini format
        """
        debug = self.gemini_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def call_api_with_context(
        self, 
        context_contents: List[Dict[str, Any]], 
        session_id: str,
        **kwargs
    ) -> types.GenerateContentResponse:
        """
        Execute direct Gemini API call with preserved context and tool integration.
        
        Performs a complete API call using pre-formatted context contents while maintaining
        original response structure integrity. Automatically retrieves session-specific tool
        schemas and applies configuration overrides for optimal API performance.
        
        Args:
            context_contents: Pre-formatted Gemini API context contents with structure:
                - role: str - Message role ("user", "model", "system")
                - parts: List[Dict] - Content parts including text and function calls
            session_id: Session ID for tool schema retrieval and dependency injection
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_output_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - top_k: Optional[int] - Top-k sampling parameter
                
        Returns:
            types.GenerateContentResponse: Raw Gemini API response with complete structure:
                - candidates: List[types.Candidate] - Response candidates with content
                - usage_metadata: types.UsageMetadata - Token usage information
                - prompt_feedback: Optional[types.PromptFeedback] - Content filtering feedback
                
        Raises:
            Exception: If API call fails, returns invalid response, or encounters authentication errors
            
        Example:
            context = [{"role": "user", "parts": [{"text": "Hello"}]}]
            response = await client.call_api_with_context(context, session_id="123")
            
        Note:
            This method integrates with GeminiToolManager for session-specific tool schemas
            and GeminiDebugger for comprehensive request/response logging when debug mode is enabled.
        """
        # Get tool schemas for the session
        tool_schemas = await self.get_function_call_schemas(session_id)
        tools_enabled = bool(tool_schemas)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        debug = self.gemini_config.debug
        
        # Build API configuration
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt,
            tool_schemas=tool_schemas
        )
        
        # Apply any kwargs overrides
        config_kwargs.update(kwargs)
        config = types.GenerateContentConfig(**config_kwargs)

        if debug:
            print(f"[DEBUG] API call with {len(context_contents)} context items")
            GeminiDebugger.print_debug_request(context_contents, config)

        try:
            # Direct API call with preserved context
            response = self.client.models.generate_content(
                model=self.gemini_config.model_settings.model,
                contents=context_contents,
                config=config,
            )
            
            # Validate response structure
            if hasattr(response, 'error'):
                error_message = f"Gemini API error: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"
                raise Exception(error_message)
            
            if not hasattr(response, 'candidates') or not response.candidates:
                raise Exception("Gemini API returned empty response")
            
            if debug:
                print(f"[DEBUG] API call successful, response received")
                GeminiDebugger.print_debug_response(response)
            
            return response
                
        except Exception as e:
            error_message = f"Gemini API call failed: {str(e)}"
            if debug:
                print(f"[DEBUG] {error_message}")
            raise Exception(error_message)

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate conversation title using Gemini API.
        Customized implementation for Gemini API supporting multimodal content.
        
        Args:
            latest_messages: Recent conversation messages to generate title from
        """
        return await GeminiTitleGenerator.generate_title_from_messages(
            self.client, latest_messages
        )

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompt using the Gemini API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
            
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.gemini_config.debug
        return await GeminiImagePromptGenerator.generate_text_to_image_prompt(self.client, session_id, debug)

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.
        
        Args:
            query: The search query to find information on the web
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        debug = self.gemini_config.debug
        return await GeminiWebSearchGenerator.perform_web_search(self.client, query, debug, **kwargs)

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========

    def _should_continue_tool_calling(self, response: Any) -> bool:
        """Check if Gemini response contains tool calls that require execution."""
        return GeminiResponseProcessor.should_continue_tool_calling(response)

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from Gemini response."""
        return GeminiResponseProcessor.extract_tool_calls(response)

    def _get_response_processor(self):
        """Get Gemini-specific response processor."""
        return GeminiResponseProcessor

    def _log_context_state(self, context_manager: Any):
        """Log Gemini context manager state for debugging."""
        # Gemini uses default logging from base class
        super()._log_context_state(context_manager)

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _execute_single_tool_call is inherited from LLMClientBase