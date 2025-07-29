"""
Anthropic client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Anthropic-specific functionality.
"""

import os
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
import json
import uuid
import time
import anthropic

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.response_models import LLMResponse
from backend.shared.utils.text_parser import parse_llm_output
from backend.config import get_system_prompt
from backend.infrastructure.mcp.smart_mcp_server import mcp as GLOBAL_MCP

# Import Anthropic-specific implementations
from .config import AnthropicClientConfig, get_anthropic_client_config
from .constants import *
from .message_formatter import MessageFormatter
from .content_generators import TitleGenerator, ImagePromptGenerator, AnalysisGenerator
from .response_processor import ResponseProcessor
from .debug import AnthropicDebugger
from .context_manager import AnthropicContextManager
from .tool_manager import AnthropicToolManager


class AnthropicClient(LLMClientBase):
    """
    Anthropic Claude client implementation using unified architecture.
    
    Inherits from LLMClientBase and implements Anthropic-specific functionality
    while leveraging shared components where possible.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Anthropic client.
        
        Args:
            api_key: Anthropic API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize Anthropic-specific configuration
        config_overrides = {}
        
        # Extract relevant configuration from extra_config for overrides
        if 'model' in self.extra_config:
            config_overrides['model_settings'] = {'model': self.extra_config['model']}
        if 'temperature' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['temperature'] = self.extra_config['temperature']
        if 'max_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['max_tokens'] = self.extra_config['max_tokens']
        if 'thinking_budget_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['thinking_budget_tokens'] = self.extra_config['thinking_budget_tokens']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.anthropic_config = get_anthropic_client_config(**config_overrides)
        
        print(f"Enhanced Anthropic Client initialized with model: {self.anthropic_config.model_settings.model}")
        
        # Initialize API client - use unified client attribute name
        self.client = anthropic.Anthropic(api_key=self.api_key)
       
        # Initialize unified tool manager
        self.tool_manager = AnthropicToolManager(
            mcp_client_source=GLOBAL_MCP,
            tools_enabled=self.tools_enabled
        )

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        Get all MCP tool schemas in Anthropic format.
        Only return meta tools + cached tools, not all regular tools.
        """
        debug = self.anthropic_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def call_api_with_context(
        self,
        anthropic_messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        Direct API call using context contents in Anthropic format.
        
        Args:
            anthropic_messages: Pre-formatted Anthropic API messages
            session_id: Optional session ID for tool schema retrieval
            **kwargs: Additional parameters for API configuration
            
        Returns:
            Raw Anthropic API response object
        """
        debug = self.anthropic_config.debug
        
        # Get tool schemas
        tools = await self.get_function_call_schemas(session_id)
        tools_enabled = bool(tools)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        # Use configuration system to build API parameters
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=anthropic_messages,
            tools=tools
        )

        if debug:
            # Log basic API call information
            AnthropicDebugger.log_api_call_info(
                tools_count=len(tools) if tools else 0,
                model=self.anthropic_config.model_settings.model,
                thinking_enabled=self.anthropic_config.model_settings.supports_thinking() and self.anthropic_config.model_settings.enable_thinking
            )
            
            # Print simplified debug payload
            AnthropicDebugger.print_debug_request_payload(kwargs_api)
        
        try:
            # Call Anthropic API
            response = self.client.messages.create(**kwargs_api)
            
            # Print raw response (if debug enabled)
            if debug:
                AnthropicDebugger.log_raw_response(response)
            
            return response
            
        except Exception as e:
            # Ensure payload information is visible even when API call fails
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                AnthropicDebugger.print_debug_request_payload(kwargs_api)
            
            # Re-raise exception
            raise

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title using the Anthropic API.
        Support multimodal content.
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        return TitleGenerator.generate_title_from_messages(
            self.client,
            first_user_message,
            first_assistant_message,
            title_generation_system_prompt
        ) 

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Anthropic API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
        
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        return ImagePromptGenerator.generate_text_to_image_prompt(
            self.client,
            session_id,
            self.anthropic_config.debug
        )

    async def perform_web_search(self, query: str, max_uses: int = 5) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.
        
        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.
        
        Args:
            query: The search query to find information on the web
            max_uses: Maximum number of search tool uses
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        from .content_generators import WebSearchGenerator
        return WebSearchGenerator.perform_web_search(
            self.client, 
            query, 
            self.anthropic_config.debug,
            max_uses
        )

    # ========== CORE STREAMING INTERFACE ==========

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        Streaming Anthropic API call - fully aligned with GeminiClient architecture.
        
        Streaming processor designed for real-time tool calling notifications using event-driven pattern:
        1. Real-time yield tool call start/progress/completion notifications
        2. Maintain complete execution tracking and error handling
        3. Final return of complete response and metadata
        4. Fully compatible with existing architecture
        
        Args:
            messages: Input message history
            session_id: Session ID for tool and context management
            max_iterations: Maximum number of tool calling iterations
            **kwargs: Additional API configuration parameters
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Intermediate notifications: tool calling status updates
            - Final result: (final_message, execution_metadata)
        """
        # === INITIALIZATION PHASE ===
        execution_id = self._generate_execution_id()
        debug = self.anthropic_config.debug

        # Create independent context manager - ensure state isolation
        context_manager = AnthropicContextManager()
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
            'tool_calls_detected': False,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE - Streaming tool calling loop ===
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
            
            # Create final storage message - use ResponseProcessor instead of context_manager
            final_message = ResponseProcessor.format_response_for_storage(final_response)
            
            # Yield final result
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            
            # Yield error notification
            yield {
                'type': 'error',
                'error': f"Anthropic execution {execution_id} failed: {e}",
                'execution_id': execution_id
            }
            
            # Send tool use concluded notification
            yield {
                'type': 'NAGISA_TOOL_USE_CONCLUDED',
                'execution_id': execution_id
            }
            
            raise Exception(f"Anthropic execution {execution_id} failed: {e}")

    async def _streaming_tool_calling_loop(
        self,
        context_manager: AnthropicContextManager,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Any], None]:
        """
        Streaming tool calling loop - core real-time notification engine fully aligned with Gemini.
        
        This is the core method implementing real-time tool calling notifications using event-driven architecture:
        1. Real-time yield notification for each tool calling phase
        2. Maintain complete state tracking and error handling
        3. Fully compatible with existing tool calling logic
        """
        execution_id = metadata['execution_id']
        
        # Get initial response
        anthropic_messages = context_manager.get_working_messages()
        current_response = await self.call_api_with_context(
            anthropic_messages, session_id=session_id, **kwargs
        )
        metadata['api_calls'] += 1
        
        # Tool calling state machine
        iteration = 0
        while iteration < max_iterations:
            metadata['iterations'] = iteration + 1
            
            # State check: whether to continue tool calling
            if not context_manager.should_continue_tool_calling_from_response(current_response):
                break
            
            # Set flag and send notification when first tool call is detected
            if not metadata['tool_calls_detected']:
                metadata['tool_calls_detected'] = True
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': 'anthropic_tools',
                    'action_text': "I am using tools to help you..."
                }
            
            # Add current response to context
            context_manager.add_response(current_response)
            
            # Extract and execute tool calls
            tool_calls = context_manager.extract_tool_calls_from_response(current_response)
            
            # Execute tool calls - real-time notification for each tool call and immediately add to context
            for tool_call in tool_calls:
                metadata['tool_calls_executed'] += 1
                
                # Tool start notification
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': tool_call.get('name', 'unknown_tool'),
                    'action_text': f"Using {tool_call.get('name', 'tool')}..."
                }
                
                # Execute single tool call
                tool_result = await self._execute_single_tool_call(
                    tool_call, session_id, execution_id, debug
                )
                
                # Tool completion notification
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': tool_call.get('name', 'unknown_tool'),
                    'action_text': f"Completed {tool_call.get('name', 'tool')}"
                }
                
                # Immediately add tool result to context - simplified implementation
                context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    tool_result
                )
            
            # Get next round response
            anthropic_messages = context_manager.get_working_messages()
            current_response = await self.call_api_with_context(
                anthropic_messages, session_id=session_id, **kwargs
            )
            metadata['api_calls'] += 1
            
            iteration += 1
        
        # Check if maximum iterations reached
        if iteration >= max_iterations:
            yield {
                'type': 'error',
                'error': f"Execution {execution_id} exceeded max iterations ({max_iterations})"
            }
            raise Exception(f"Execution {execution_id} exceeded max iterations ({max_iterations})")
        
        # Tool calling end notification
        if metadata['tool_calls_detected']:
            if metadata['tool_calls_executed'] == 1:
                complete_text = "I have completed the requested action."
            else:
                complete_text = f"I used {metadata['tool_calls_executed']} tools to help you."
            
            yield {
                'type': 'NAGISA_IS_USING_TOOL',
                'tool_name': 'anthropic_tools',
                'action_text': complete_text
            }
        
        # Final notification
        yield {
            'type': 'NAGISA_TOOL_USE_CONCLUDED',
            'execution_id': execution_id
        }
        
        # Return final response
        yield current_response

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        execution_id: str,
        debug: bool
    ) -> Any:
        """
        Execute single tool call - atomic operation.
        
        Tool execution method designed for streaming architecture, supporting:
        1. Atomic tool call execution
        2. Complete error handling and recovery
        3. Debug information output
        4. Session-level context management
        
        Args:
            tool_call: Tool call dictionary containing name, arguments, id
            session_id: Session ID for context management
            execution_id: Execution ID for debug tracking
            debug: Debug mode switch
            
        Returns:
            Tool execution result, or error message string
        """
        try:
            if debug:
                print(f"[DEBUG] Executing tool: {tool_call.get('name', 'unknown')} in execution {execution_id}")
            
            result = await self.tool_manager.handle_function_call(
                tool_call, session_id, debug
            )
            
            if debug:
                print(f"[DEBUG] Tool execution completed: {tool_call.get('name', 'unknown')}")
            
            return result
            
        except Exception as e:
            error_result = f"Tool execution failed: {str(e)}"
            
            if debug:
                print(f"[DEBUG] Tool execution failed: {tool_call.get('name', 'unknown')} - {str(e)}")
            
            return error_result