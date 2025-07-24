import os
from typing import List, Optional, Dict, Any, AsyncGenerator, Union
import json
import uuid
import time
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse, ToolResultMessage, UserMessage
from backend.chat.utils import parse_llm_output
import anthropic
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.utils import extract_text_from_mcp_result
from backend.config import get_system_prompt
from backend.nagisa_mcp.smart_mcp_server import mcp as GLOBAL_MCP
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult
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
    Anthropic Claude 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化 Anthropic 客户端。
        Args:
            api_key: Anthropic API key。
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize Anthropic-specific configuration
        config_overrides = {}
        
        # 从extra_config中提取相关配置进行覆盖
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
        
        # 初始化API客户端 - 使用统一的client属性名
        self.client = anthropic.Anthropic(api_key=self.api_key)
       
        # 初始化统一工具管理器
        self.tool_manager = AnthropicToolManager(
            mcp_client_source=GLOBAL_MCP,
            tools_enabled=self.tools_enabled
        )

    def _clear_session_tool_cache(self, session_id: str):
        """清除会话的工具缓存"""
        self.tool_manager.clear_session_tool_cache(session_id)



    def _format_llm_response(self, response) -> LLMResponse:
        """
        Format Anthropic API response into LLMResponse object.
        
        Args:
            response: Raw response from Anthropic API
            
        Returns:
            LLMResponse object containing the formatted response
        """
        if not hasattr(response, "content") or not response.content:
            return LLMResponse(content=[{"type": "text", "text": ""}])

        tool_calls = []
        llm_content = []
        llm_reply = ""

        for item in response.content:
            item_dict = {"type": item.type}
            if item.type == "text":
                item_dict["text"] = item.text
                llm_reply += item.text
            elif item.type == "tool_use":
                item_dict["name"] = item.name
                item_dict["input"] = item.input
                item_dict["id"] = item.id
                tool_calls.append({
                    'name': item.name,
                    'arguments': item.input,
                    'id': item.id
                })
            elif item.type == "thinking":
                item_dict["thinking"] = item.thinking
                item_dict["signature"] = item.signature
            elif item.type == "redacted_thinking":
                pass
            
            llm_content.append(item_dict)

        response_text, keyword = parse_llm_output(llm_reply)
        
        return LLMResponse(
            content=llm_content,
            keyword=keyword
        )

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        **kwargs
    ):
        """
        流式Anthropic API调用 - 兼容GeminiClient架构
        
        返回AsyncGenerator，yield中间通知和最终结果元组
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - 中间通知: 工具调用状态更新
            - 最终结果: (final_message, execution_metadata)
        """
        
        execution_id = str(uuid.uuid4())[:8]
        debug = self.anthropic_config.debug
        
        # 初始化执行元数据
        metadata = {
            'execution_id': execution_id,
            'session_id': session_id,
            'start_time': time.time(),
            'end_time': None,
            'iterations': 0,
            'api_calls': 0,
            'tool_calls_executed': 0,
            'tool_calls_detected': False,
            'status': 'running'
        }
        
        if debug:
            print(f"[AnthropicClient] Starting execution {execution_id}")
        
        try:
            # 创建上下文管理器并初始化
            context_manager = AnthropicContextManager()
            context_manager.initialize_from_messages(messages)
            
            # 流式工具调用循环
            final_message = None
            iteration = 0
            current_messages = messages.copy()
            
            while iteration < max_iterations:
                iteration += 1
                metadata['iterations'] = iteration
                
                if debug:
                    print(f"[AnthropicClient] Iteration {iteration}")
                
                # 使用上下文管理器获取工作消息
                anthropic_messages = context_manager.get_working_messages()
                
                # 获取工具schemas
                tools = await self.tool_manager.get_function_call_schemas(session_id, debug)
                tools_enabled = bool(tools)
                system_prompt = get_system_prompt(tools_enabled=tools_enabled)
                
                # 使用配置系统构建API参数
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
                    
                    # Print simplified debug payload (similar to Gemini client)
                    AnthropicDebugger.print_debug_request_payload(kwargs_api)
                
                # 发送请求开始通知
                yield {
                    'type': 'NAGISA_TOOL_USE_STARTED',
                    'execution_id': execution_id,
                    'iteration': iteration
                }
                
                # 调用Anthropic API
                metadata['api_calls'] += 1
                response = self.client.messages.create(**kwargs_api)
                
                # 将响应添加到上下文管理器
                context_manager.add_response(response)
                context_manager.increment_iteration()
                
                # 提取工具调用
                tool_calls = context_manager.extract_tool_calls_from_latest_response()
                
                if tool_calls:
                    # 首次检测到工具调用时设置标志并发送通知
                    if not metadata['tool_calls_detected']:
                        metadata['tool_calls_detected'] = True
                        yield {
                            'type': 'NAGISA_IS_USING_TOOL',
                            'tool_name': 'anthropic_tools',
                            'action_text': "I am using tools to help you..."
                        }
                    
                    tool_results = []
                    
                    # 执行每个工具调用
                    for tool_call in tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['arguments'] 
                        tool_id = tool_call['id']
                        
                        # 发送工具开始通知（匹配GeminiClient格式）
                        yield {
                            'type': 'NAGISA_IS_USING_TOOL',
                            'tool_name': tool_name,
                            'action_text': f"Using {tool_name}..."
                        }
                        
                        # 执行单个工具调用
                        tool_result = await self._execute_single_tool_call(
                            tool_call, session_id, execution_id, debug
                        )
                        
                        metadata['tool_calls_executed'] += 1
                        
                        # 将工具结果添加到上下文管理器
                        context_manager.add_tool_result(tool_id, tool_name, tool_result)
                        
                        # 发送工具完成通知（匹配GeminiClient格式）
                        tool_action_text = f"Completed {tool_name}" if not isinstance(tool_result, str) or not tool_result.startswith("Tool execution failed") else f"Failed {tool_name}"
                        yield {
                            'type': 'NAGISA_IS_USING_TOOL',
                            'tool_name': tool_name,
                            'action_text': tool_action_text
                        }
                        
                        # 创建工具结果消息
                        is_error = isinstance(tool_result, str) and tool_result.startswith("Tool execution failed")
                        tool_result_content = {"error": tool_result, "is_error": True} if is_error else tool_result
                        
                        tool_result_msg = ToolResultMessage(
                            role="tool",
                            name=tool_name,
                            content=tool_result_content,
                            tool_call_id=tool_id
                        )
                        tool_results.append(tool_result_msg)
                    
                    # 将工具调用响应和工具结果添加到消息历史
                    # Anthropic 不需要单独的 AssistantToolMessage，直接创建 AssistantMessage
                    from backend.chat.models import AssistantMessage
                    
                    # 创建包含 tool_use 块的内容
                    response_content = []
                    
                    # 添加响应中的所有内容（text, thinking, tool_use等）
                    for item in response.content:
                        if item.type == "text":
                            response_content.append({"type": "text", "text": item.text})
                        elif item.type == "tool_use":
                            response_content.append({
                                "type": "tool_use",
                                "id": item.id,
                                "name": item.name,
                                "input": item.input
                            })
                        elif item.type == "thinking":
                            response_content.append({
                                "type": "thinking", 
                                "thinking": item.thinking
                            })
                    
                    assistant_msg = AssistantMessage(
                        role="assistant",
                        content=response_content
                    )
                    current_messages.append(assistant_msg)
                    current_messages.extend(tool_results)
                    
                    # 继续下一轮迭代
                    continue
                else:
                    # 没有工具调用，结束循环
                    final_message = context_manager.finalize_and_get_storage_message(response)
                    break
            
            # 发送工具调用总结通知（匹配GeminiClient）
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
            
            # 发送工具使用结束通知
            yield {
                'type': 'NAGISA_TOOL_USE_CONCLUDED',
                'execution_id': execution_id
            }
            
            # 完成执行
            metadata['status'] = 'completed'
            metadata['end_time'] = time.time()
            
            if debug:
                print(f"[AnthropicClient] Execution {execution_id} completed in {iteration} iterations")
            
            # 返回最终结果
            if final_message is None:
                from backend.chat.models import AssistantMessage
                final_message = AssistantMessage(
                    role="assistant",
                    content=[{"type": "text", "text": "Maximum iterations reached."}]
                )
            
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = time.time()
            
            if debug:
                print(f"[AnthropicClient] Execution {execution_id} failed: {e}")
            
            # 发送错误通知
            yield {
                'type': 'error',
                'error': f"Anthropic execution {execution_id} failed: {e}",
                'execution_id': execution_id
            }
            
            # 发送工具使用结束通知
            yield {
                'type': 'NAGISA_TOOL_USE_CONCLUDED',
                'execution_id': execution_id
            }
            
            raise Exception(f"Anthropic execution {execution_id} failed: {e}")

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        execution_id: str,
        debug: bool
    ) -> Any:
        """
        执行单个工具调用 - 原子性操作
        
        专为流式架构设计的工具执行方法，支持：
        1. 原子性工具调用执行
        2. 完整的错误处理和恢复
        3. 调试信息输出
        4. 会话级别的上下文管理
        
        Args:
            tool_call: 工具调用字典，包含 name, arguments, id
            session_id: 会话ID，用于上下文管理
            execution_id: 执行ID，用于调试追踪
            debug: 调试模式开关
            
        Returns:
            工具执行结果，或错误信息字符串
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

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title using the Anthropic API.
        支持多模态 content。
        
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

