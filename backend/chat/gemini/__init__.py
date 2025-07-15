"""
Gemini API client module.

This module provides a modular Gemini client implementation with separated concerns:
- GeminiClient: Enhanced client with original context preservation for tool calling
- GeminiContextManager: Context management for tool calling with original response preservation
- GeminiDebugger: Debug utilities for request/response inspection
- MessageFormatter: Message format conversion utilities
- ResponseProcessor: Enhanced dual-mode response processing with context preservation
- ToolManager: MCP tool integration and management
- TitleGenerator: Conversation title generation
- ImagePromptGenerator: Text-to-image prompt generation

Key Features:
- **Original Context Preservation**: Maintains complete API response integrity during tool calling
- **Dual-mode Response Processing**: Context preservation + storage optimization
- **Advanced Tool Calling**: Complete tool calling sequences with context management
- **Thinking Chain Preservation**: Full thinking content and validation field integrity
- **Performance Optimization**: Efficient API calls and context management
- **Full Backward Compatibility**: Legacy methods continue to work seamlessly

Enhanced Architecture:
- Context-preservation mode for multi-turn tool calling
- Storage-optimized mode for message history
- Advanced state analysis and validation field extraction
- Comprehensive error handling and performance monitoring
- Complete integration of GeminiContextManager and dual-mode ResponseProcessor

Usage Patterns:
1. Legacy mode: `client.get_response(messages)` - Traditional processing
2. Context-preservation mode: `client.get_response_with_context_preservation(messages)` - Raw response + context manager
3. Enhanced mode: `client.get_enhanced_response(messages)` - Universal handler for all request types with metadata
"""

from .client import GeminiClient
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .message_formatter import MessageFormatter
from .response_processor import ResponseProcessor
from .tool_manager import ToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator

__all__ = [
    'GeminiClient',
    'GeminiContextManager',
    'GeminiDebugger',
    'MessageFormatter',
    'ResponseProcessor',
    'ToolManager',
    'TitleGenerator',
    'ImagePromptGenerator'
] 