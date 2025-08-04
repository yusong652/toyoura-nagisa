"""
OpenAI client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and provides
full OpenAI GPT integration with streaming, tool calling, and content generation.
"""

from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
import json
from openai import OpenAI
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.config import get_system_prompt

# Import OpenAI-specific implementations
from .config import get_openai_client_config
from .context_manager import OpenAIContextManager
from .debug import OpenAIDebugger
from .response_processor import OpenAIResponseProcessor
from .tool_manager import OpenAIToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator, WebSearchGenerator


class OpenAIClient(LLMClientBase):
    """
    OpenAI GPT client implementation using unified architecture.
    
    Key Features:
    - Inherits from unified LLMClientBase
    - Full streaming support with tool calling
    - Real-time tool execution notifications
    - Content generation capabilities
    - Comprehensive error handling
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize OpenAI-specific configuration
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
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.openai_config = get_openai_client_config(**config_overrides)
        
        print(f"Enhanced OpenAI Client initialized with model: {self.openai_config.model_settings.model}")
        
        # Initialize API client - using unified client attribute name
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize unified tool manager
        self.tool_manager = OpenAIToolManager(tools_enabled=self.tools_enabled)

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all MCP tool schemas in OpenAI format.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in OpenAI format
        """
        debug = getattr(self, 'debug', False)  # Fallback for debug flag
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        Execute direct OpenAI API call with context and tool integration.
        
        Performs a complete API call using pre-formatted context contents while maintaining
        original response structure. Automatically retrieves session-specific tool
        schemas and applies configuration overrides for optimal performance.
        
        Args:
            context_contents: Pre-formatted OpenAI API messages with structure:
                - role: str - Message role ("user", "assistant", "system", "tool")
                - content: str - Message content
                - tool_calls: Optional[List] - Tool calls from assistant
                - tool_call_id: Optional[str] - ID for tool responses
            session_id: Session ID for tool schema retrieval and dependency injection
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - stream: Optional[bool] - Enable streaming response
                
        Returns:
            OpenAI ChatCompletion response object with structure:
                - choices: List[Choice] - Response candidates
                - usage: Usage - Token usage information
                - model: str - Model used for completion
                
        Raises:
            Exception: If API call fails or returns invalid response
        """
        debug = self.openai_config.debug
        
        # Get tool schemas for the session
        tools = await self.tool_manager.get_function_call_schemas(session_id, debug)
        tools_enabled = bool(tools)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        # Build API configuration
        kwargs_api = self.openai_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )
        
        # Apply any kwargs overrides
        if 'temperature' in kwargs:
            kwargs_api['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            kwargs_api['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            kwargs_api['top_p'] = kwargs['top_p']
        
        if debug:
            # Log basic API call information
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools) if tools else 0,
                model=self.openai_config.model_settings.model
            )
            
            # Print simplified debug payload
            OpenAIDebugger.print_debug_request_payload(kwargs_api)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(**kwargs_api)
            
            # Print raw response (if debug enabled)
            if debug:
                OpenAIDebugger.log_raw_response(response)
            
            return response
            
        except Exception as e:
            # Ensure payload info is visible on API call failure
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                OpenAIDebugger.print_debug_request_payload(kwargs_api)
            
            # Re-raise exception
            raise

    # ========== CORE STREAMING INTERFACE ==========

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        Streaming OpenAI API call with real-time tool calling notifications.
        
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
        debug = self.openai_config.debug

        # Create independent context manager - ensure state isolation
        context_manager = OpenAIContextManager()
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
            
            # Extract keyword - extract from original response before formatting
            original_text = OpenAIResponseProcessor.extract_text_content(final_response)
            from backend.shared.utils.text_parser import parse_llm_output
            _, extracted_keyword = parse_llm_output(original_text)
            metadata['keyword'] = extracted_keyword
            
            # Create final storage message - use ResponseProcessor instead of context_manager
            final_message = OpenAIResponseProcessor.format_response_for_storage(final_response)
            
            # Yield final result
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            
            # Yield error notification
            yield {
                'type': 'error',
                'error': f"OpenAI execution {execution_id} failed: {e}",
                'execution_id': execution_id
            }
            
            # Send tool use conclusion notification
            yield {
                'type': 'NAGISA_TOOL_USE_CONCLUDED',
                'execution_id': execution_id
            }
            
            raise Exception(f"OpenAI execution {execution_id} failed: {e}")

    async def _streaming_tool_calling_loop(
        self,
        context_manager: OpenAIContextManager,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Any], None]:
        """
        Streaming tool calling loop - core real-time notification engine.
        
        This is the core method implementing real-time tool calling notifications using event-driven architecture:
        1. Real-time yield notification for each tool calling phase
        2. Maintain complete state tracking and error handling
        3. Fully compatible with existing tool calling logic
        """
        execution_id = metadata['execution_id']
        
        # Get initial response
        openai_messages = context_manager.get_working_contents()
        current_response = await self.call_api_with_context(
            openai_messages, session_id=session_id, **kwargs
        )
        metadata['api_calls'] += 1
        
        # Tool calling state machine
        iteration = 0
        while iteration < max_iterations:
            metadata['iterations'] = iteration + 1
            
            # State check: whether to continue tool calling
            if not OpenAIResponseProcessor.should_continue_tool_calling(current_response):
                break
            
            # Set flag and send notification when first tool call is detected
            if not metadata['tool_calls_detected']:
                metadata['tool_calls_detected'] = True
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': 'openai_tools',
                    'action_text': "I am using tools to help you..."
                }
            
            # Add current response to context
            context_manager.add_response(current_response)
            
            # Extract and execute tool calls
            tool_calls = OpenAIResponseProcessor.extract_tool_calls(current_response)
            
            # Execute tool calls - real-time notification for each tool call
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
                
                # Immediately add tool result to context
                context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    tool_result
                )
            
            # Get next round response
            openai_messages = context_manager.get_working_contents()
            current_response = await self.call_api_with_context(
                openai_messages, session_id=session_id, **kwargs
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
                'tool_name': 'openai_tools',
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
        Execute single tool call with comprehensive error handling.
        
        Performs atomic tool execution with proper separation between business logic
        errors (handled by the tool layer) and system-level errors (propagated to caller).
        
        Args:
            tool_call: Tool call specification with structure:
                - id: str - Unique tool call identifier
                - name: str - Tool name to execute
                - arguments: Dict[str, Any] - Tool parameters
            session_id: Session ID for context-specific tool execution
            execution_id: Unique execution identifier for debugging and tracking
            debug: Enable detailed debug logging
            
        Returns:
            Any: Tool execution result in standardized ToolResult format:
                - Business logic errors: Formatted error ToolResult from tool layer
                - Successful execution: Tool-specific result data
                
        Raises:
            Exception: System-level errors (network, memory, code bugs) that cannot be
                      handled by the tool layer and should not be passed to LLM
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

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate conversation title using OpenAI API.
        
        Args:
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if failed
        """
        return await TitleGenerator.generate_title_from_messages(
            self.client,
            latest_messages
        )

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate text-to-image prompt using OpenAI API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
            
        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed
        """
        debug = self.openai_config.debug
        return await ImagePromptGenerator.generate_text_to_image_prompt(
            self.client,
            session_id,
            debug
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform web search using OpenAI API with tools.
        
        Note: OpenAI doesn't have built-in web search like Gemini, so this
        uses MCP tools for web search functionality.
        
        Args:
            query: Search query to find information on the web
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        debug = self.openai_config.debug
        return await WebSearchGenerator.perform_web_search(
            self.client,
            query,
            debug,
            **kwargs
        )