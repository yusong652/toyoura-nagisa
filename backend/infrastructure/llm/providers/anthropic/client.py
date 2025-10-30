from typing import List, Optional, Dict, Any, AsyncGenerator
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.streaming import StreamingChunk
import anthropic
from .config import get_anthropic_client_config
from .response_processor import AnthropicResponseProcessor
from .debug import AnthropicDebugger
from .context_manager import AnthropicContextManager
from .tool_manager import AnthropicToolManager

class AnthropicClient(LLMClientBase):
    """
    Anthropic Claude client class.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize AnthropicClient instance.
        Args:
            api_key: Anthropic API key。
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize Anthropic-specific configuration
        config_overrides = {}
        
        # Apply any extra configuration overrides
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
        if 'enable_thinking' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['enable_thinking'] = self.extra_config['enable_thinking']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.anthropic_config = get_anthropic_client_config(**config_overrides)
        
        print(f"Enhanced Anthropic Client initialized with model: {self.anthropic_config.model_settings.model}")

        # initialize Anthropic API client (use async client for streaming)
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # initialize tool manager
        self.tool_manager = AnthropicToolManager()


    def _get_response_processor(self) -> Optional['AnthropicResponseProcessor']:
        """Get Anthropic-specific response processor instance."""
        return AnthropicResponseProcessor()

    def _get_context_manager_class(self):
        """Get Anthropic-specific context manager class."""
        return AnthropicContextManager

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless Anthropic API call.

        This method consolidates all context preparation logic for Anthropic
        and returns all necessary configuration for thread-safe API calls.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Messages for Anthropic API (without system prompt)
            - api_config: Dictionary with 'tools' and 'system_prompt' keys
        """
        # Get context manager and extract its properties
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Get tool schemas for API
        tool_schemas = await self.tool_manager.get_function_call_schemas(session_id, agent_profile)

        # Get tool schemas formatted for system prompt
        prompt_tool_schemas = await self.tool_manager.get_schemas_for_system_prompt(session_id, agent_profile)

        # Build system prompt with tool schemas and memory
        from backend.shared.utils.prompt.builder import build_system_prompt

        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )

        # Get working contents from context manager (config obtained internally)
        working_contents = context_manager.get_working_contents()

        # Return context and config as separate values for thread-safe API call
        api_config = {
            'tools': tool_schemas,
            'system_prompt': system_prompt
        }
        return working_contents, api_config

    def _get_provider_config(self):
        """Get Anthropic-specific configuration object."""
        return self.anthropic_config

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ):
        """
        Execute direct Anthropic API call with complete pre-formatted context and config.

        Performs a stateless API call using provided context and configuration.
        This method is thread-safe and supports concurrent sessions.

        Args:
            context_contents: Complete Anthropic context contents with messages
            api_config: Anthropic-specific configuration dictionary:
                - tools: List[Dict] - Tool schemas in Anthropic format
                - system_prompt: str - System prompt for Anthropic
            **kwargs: Additional API configuration parameters

        Returns:
            Anthropic API response

        Note:
            This method is completely stateless. All configuration is passed via parameters.
        """
        debug = self.anthropic_config.debug

        # Extract configuration from api_config
        tools = api_config.get('tools', [])
        system_prompt = api_config.get('system_prompt', '')

        # 使用配置系统构建API参数
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )

        # Apply any additional kwargs
        kwargs_api.update(kwargs)

        try:
            # call the Anthropic API (async)
            response = await self.client.messages.create(**kwargs_api)

            return response

        except Exception as e:
            # Log debug information if in debug mode
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                AnthropicDebugger.print_debug_request_payload(kwargs_api)

            raise e

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Anthropic API call with real-time chunk delivery.

        Streams responses from Anthropic API and converts native chunks into
        standardized StreamingChunk objects for consistent handling.

        Args:
            context_contents: Complete Anthropic context contents with messages
            api_config: Anthropic-specific configuration dictionary:
                - tools: List[Dict] - Tool schemas in Anthropic format
                - system_prompt: str - System prompt for Anthropic
            **kwargs: Additional API parameters (temperature, max_tokens, etc.)

        Yields:
            StreamingChunk: Standardized streaming chunks containing thinking,
                          text, or function_call content

        Raises:
            Exception: If streaming API call fails
        """
        debug = self.anthropic_config.debug

        # Extract configuration from api_config
        tools = api_config.get('tools', [])
        system_prompt = api_config.get('system_prompt', '')

        # Build API parameters using configuration system
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )

        # Apply any additional kwargs
        kwargs_api.update(kwargs)

        if debug:
            print(f"[DEBUG] Streaming API call with {len(context_contents)} messages")
            AnthropicDebugger.print_debug_request_payload(kwargs_api)

        try:
            # Track thinking signature for current thinking block
            current_thinking_signature: Optional[str] = None
            current_block_type: Optional[str] = None  # Track current content block type

            # Track current tool call being streamed
            current_tool_id: Optional[str] = None
            current_tool_name: Optional[str] = None
            accumulated_tool_json: str = ""

            # Use Anthropic's async streaming context manager
            async with self.client.messages.stream(**kwargs_api) as stream:
                async for event in stream:
                    # Track content block start to know what type we're in
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, 'type'):
                            current_block_type = event.content_block.type
                            # Only ToolUseBlock has id and name attributes
                            if current_block_type == "tool_use" and hasattr(event.content_block, 'id') and hasattr(event.content_block, 'name'):
                                current_tool_id = event.content_block.id  # type: ignore
                                current_tool_name = event.content_block.name  # type: ignore
                                accumulated_tool_json = ""

                    # Thinking content
                    elif event.type == "thinking":
                        yield StreamingChunk(
                            chunk_type="thinking",
                            content=event.thinking,
                            metadata={"snapshot": event.snapshot}
                        )

                    # Text content
                    elif event.type == "text":
                        yield StreamingChunk(
                            chunk_type="text",
                            content=event.text,
                            metadata={"snapshot": event.snapshot}
                        )

                    # Signature event (for thinking blocks)
                    elif event.type == "signature":
                        current_thinking_signature = event.signature

                    # Tool parameters (partial JSON)
                    elif event.type == "input_json":
                        if current_tool_id:
                            accumulated_tool_json += event.partial_json

                    # Content block complete
                    elif event.type == "content_block_stop":
                        # If this was a tool use block, emit the complete tool call
                        if current_tool_id and current_tool_name:
                            # Parse accumulated JSON
                            import json
                            try:
                                tool_input = json.loads(accumulated_tool_json) if accumulated_tool_json else {}
                            except json.JSONDecodeError:
                                tool_input = {}

                            yield StreamingChunk(
                                chunk_type="function_call",
                                content=current_tool_name,
                                metadata={
                                    "tool_id": current_tool_id,
                                    "tool_name": current_tool_name,
                                    "tool_input": tool_input
                                },
                                thought_signature=current_thinking_signature.encode() if current_thinking_signature else None,
                                function_call={
                                    "name": current_tool_name,
                                    "args": tool_input,
                                    "id": current_tool_id
                                }
                            )

                            # Reset tool tracking
                            current_tool_id = None
                            current_tool_name = None
                            accumulated_tool_json = ""
                            current_thinking_signature = None
                            current_block_type = None

                        # If this was a thinking block and we have a signature, emit a marker chunk
                        elif current_block_type == "thinking" and current_thinking_signature:
                            # Emit a special chunk to mark the end of thinking with signature
                            yield StreamingChunk(
                                chunk_type="thinking",
                                content="",  # Empty content, just carrying the signature
                                metadata={"is_signature_marker": True},
                                thought_signature=current_thinking_signature.encode()
                            )
                            current_thinking_signature = None
                            current_block_type = None
                        else:
                            # Reset for other block types
                            current_block_type = None

            if debug:
                print("[DEBUG] Streaming completed successfully")

        except Exception as e:
            if debug:
                print(f"[DEBUG] Streaming API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                AnthropicDebugger.print_debug_request_payload(kwargs_api)

            raise e

    def _construct_response_from_streaming_chunks(
        self,
        chunks: List[StreamingChunk]
    ) -> anthropic.types.Message:
        """
        Construct Anthropic Message object from collected streaming chunks.

        Converts list of StreamingChunk objects back into Anthropic's native
        Message format for tool call detection and context management.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            anthropic.types.Message: Complete Anthropic Message object with
                                     all content blocks preserved for tool calling

        Note:
            This reconstruction preserves all essential fields including:
            - Thinking content with signatures
            - Text content
            - Tool use blocks with IDs and inputs
            - All metadata needed for tool calling logic
        """
        content_blocks = []

        # Track accumulated content for each type
        accumulated_thinking = ""
        accumulated_text = ""
        current_thinking_signature: Optional[str] = None

        for chunk in chunks:
            if chunk.chunk_type == "thinking":
                # Only accumulate non-empty content (skip signature markers)
                if chunk.content or not chunk.metadata.get("is_signature_marker"):
                    accumulated_thinking += chunk.content
                # Store signature if present
                if chunk.thought_signature:
                    current_thinking_signature = chunk.thought_signature.decode()

            elif chunk.chunk_type == "text":
                # If we have accumulated thinking, add it as a block first
                if accumulated_thinking:
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": accumulated_thinking,
                        "signature": current_thinking_signature or ""
                    })
                    accumulated_thinking = ""
                    current_thinking_signature = None

                accumulated_text += chunk.content

            elif chunk.chunk_type == "function_call":
                # Add any accumulated thinking first
                if accumulated_thinking:
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": accumulated_thinking,
                        "signature": current_thinking_signature or ""
                    })
                    accumulated_thinking = ""
                    current_thinking_signature = None

                # Add any accumulated text
                if accumulated_text:
                    content_blocks.append({
                        "type": "text",
                        "text": accumulated_text
                    })
                    accumulated_text = ""

                # Add tool use block
                content_blocks.append({
                    "type": "tool_use",
                    "id": chunk.metadata.get("tool_id", ""),
                    "name": chunk.metadata.get("tool_name", ""),
                    "input": chunk.metadata.get("tool_input", {})
                })

        # Add any remaining accumulated content
        if accumulated_thinking:
            content_blocks.append({
                "type": "thinking",
                "thinking": accumulated_thinking,
                "signature": current_thinking_signature or ""
            })
        if accumulated_text:
            content_blocks.append({
                "type": "text",
                "text": accumulated_text
            })

        # Construct Message object
        # Note: We use minimal required fields for reconstruction
        return anthropic.types.Message(
            id="reconstructed",
            content=content_blocks,
            model=self.anthropic_config.model_settings.model,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=anthropic.types.Usage(
                input_tokens=0,
                output_tokens=0
            )
        )
