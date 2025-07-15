import os
from typing import List, Optional, Dict, Any

from google import genai
from google.genai import types

from backend.config import get_llm_specific_config, get_system_prompt
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse, ResponseType
from .debug import GeminiDebugger
from .message_formatter import MessageFormatter
from .response_processor import ResponseProcessor
from .tool_manager import ToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator

class GeminiClient(LLMClientBase):
    """
    Google Gemini client implementation using the new google-genai SDK.
    
    Refactored for better code organization with separated concerns:
    - GeminiDebugger: handles debug output
    - MessageFormatter: handles message formatting
    - ResponseProcessor: handles response processing
    - ToolManager: handles tool management
    - Content Generators: handle specialized content generation
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Gemini client with component-based architecture.
        
        Args:
            api_key: Google API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.client = genai.Client(api_key=api_key)
        self.safety_settings = [
            {
                "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            }
        ]
        
        print(f"Gemini Client initialized with model: {self.extra_config.get('model', 'gemini-1.5-flash-latest')}")

        # Initialize component managers
        self.tool_manager = ToolManager(tools_enabled=self.tools_enabled)
        self.debugger = GeminiDebugger()
        self.message_formatter = MessageFormatter()
        self.response_processor = ResponseProcessor()
        self.title_generator = TitleGenerator()
        self.image_prompt_generator = ImagePromptGenerator()


    # Backward compatibility: delegate to component managers
    def _get_mcp_client(self, session_id: Optional[str] = None):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.get_mcp_client(session_id)
    
    def _is_meta_tool(self, tool_name: str) -> bool:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.is_meta_tool(tool_name)
    
    def _cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.cache_tools_for_session(session_id, tools)
    
    def _get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.get_cached_tools_for_session(session_id)
    
    def _clear_session_tool_cache(self, session_id: str):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.clear_session_tool_cache(session_id)

    def map_role(self, role: str) -> str:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.map_role(role)

    def _process_inline_data(self, inline_data: Dict[str, Any]) -> Optional[types.Blob]:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.process_inline_data(inline_data)

    def _format_messages_for_gemini(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.format_messages_for_gemini(messages)

    def _format_llm_response(self, response) -> LLMResponse:
        """Backward compatibility method - delegates to ResponseProcessor."""
        return ResponseProcessor.format_llm_response(response)

    # Backward compatibility: delegate debug methods to GeminiDebugger
    def _print_debug_request(self, contents, config):
        """Backward compatibility method - delegates to GeminiDebugger."""
        return GeminiDebugger.print_debug_request(contents, config)
    
    def _print_debug_response(self, response):
        """Backward compatibility method - delegates to GeminiDebugger."""
        return GeminiDebugger.print_debug_response(response)
    
    def _sanitize_jsonschema(self, schema: dict) -> dict:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.sanitize_jsonschema(schema)

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini tools 格式列表
        只返回 meta tools + cached tools，不返回所有 regular tools。
        """
        debug = self.extra_config.get('debug', False)
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> 'LLMResponse':
        # 1. 获取所有工具 schemas（包括 MCP 工具和代码执行工具）
        tool_schemas = await self.get_function_call_schemas(session_id)
        
        tools_enabled = bool(tool_schemas)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        debug = self.extra_config.get('debug', False)

        # 2. 构造 Gemini API payload，注册 tools
        contents = MessageFormatter.format_messages_for_gemini(messages)
        config_kwargs = dict(
            system_instruction=system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 2.0),
            max_output_tokens=self.extra_config.get('max_output_tokens', 4096),
            tools=tool_schemas,
        )
        if self.extra_config.get('model', "").startswith("gemini-2.5"):
            config_kwargs["thinking_config"] = types.ThinkingConfig(include_thoughts=True)
        config = types.GenerateContentConfig(**config_kwargs)

        if debug:
            GeminiDebugger.print_debug_request(contents, config)

        try:
            # For GenerativeModel, we call generate_content directly on the model instance
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config,
            )
            
            # 检查响应中是否有错误
            if hasattr(response, 'error'):
                error_message = f"Gemini API error: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # 检查响应是否为空
            if not hasattr(response, 'candidates') or not response.candidates:
                error_message = "Gemini API returned empty response"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # Debug输出完整的LLM response
            if debug:
                GeminiDebugger.print_debug_response(response)
            
            return ResponseProcessor.format_llm_response(response)
                
        except Exception as e:
            error_message = f"Gemini API error: {str(e)}"
            print(f"[DEBUG] llm_response type: error")
            print(f"[DEBUG] {error_message}")
            if hasattr(e, 'status_code'):
                error_message += f" (Status code: {e.status_code})"
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    import json
                    error_details = json.loads(e.response.text)
                    if 'error' in error_details:
                        error_message += f"\nDetails: {error_details['error'].get('message', str(error_details))}"
                except:
                    error_message += f"\nRaw error: {e.response.text}"
            
            return LLMResponse(
                content=error_message,
                response_type=ResponseType.ERROR
            )

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        根据对话的第一轮消息生成一个简洁的对话标题。
        为Gemini API定制的实现，支持多模态 content。
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        return TitleGenerator.generate_title_from_messages(
            self.client, first_user_message, first_assistant_message, title_generation_system_prompt
        )

    def convert_mcp_schema_to_gemini(self, schema: dict) -> dict:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.convert_mcp_schema_to_gemini(schema)

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        session_id: 可选的会话ID，用于需要会话上下文的工具（如文生图）
        """
        debug = self.extra_config.get('debug', False)
        return await self.tool_manager.handle_function_call(function_call, session_id, debug)

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Gemini API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        Args:
            session_id: Optional session ID to get the latest conversation context
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.extra_config.get('debug', False)
        return ImagePromptGenerator.generate_text_to_image_prompt(self.client, session_id, debug) 