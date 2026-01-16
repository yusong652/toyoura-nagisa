/**
 * Chat message types and interfaces.
 *
 * This module defines the core message structure used throughout the application,
 * now unified with backend role naming conventions.
 */

import type { TokenUsage } from './session';

// =====================
// Message Role Types
// =====================

/**
 * Message role type - unified with backend standards.
 *
 * Aligned with LLM API conventions (OpenAI, Anthropic, Google):
 * - 'user': User-generated messages
 * - 'assistant': AI assistant responses
 * - 'image': System-generated image messages
 * - 'video': System-generated video messages
 */
export type MessageRole = 'user' | 'assistant' | 'image' | 'video';

// =====================
// Content Block Types
// =====================

/**
 * Union type for all content block variants.
 *
 * Messages can contain structured content blocks for multimodal support,
 * including text, tool calls, tool results, and thinking processes.
 */
export type ContentBlock =
  | TextBlock
  | ToolUseBlock
  | ToolResultBlock
  | ThinkingBlock;

/**
 * Plain text content block.
 */
export interface TextBlock {
  type: 'text';
  text: string;
}

/**
 * Tool invocation block (function call).
 *
 * Represents an AI assistant's decision to call a tool/function.
 */
export interface ToolUseBlock {
  type: 'tool_use';
  id: string | null;
  name: string;
  input: Record<string, any>;
}

/**
 * Tool execution result block.
 *
 * Contains the output from a tool execution, returned as a user message.
 */
export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string | null;
  tool_name: string;
  content: {
    parts: Array<{ type: string; text: string }>;
  };
  is_error: boolean;
}

/**
 * AI thinking/reasoning block.
 *
 * Contains internal reasoning process from models with extended thinking.
 */
export interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
}

// =====================
// Message Interface
// =====================

/**
 * Core message interface.
 *
 * Represents a single message in the chat, supporting both simple text
 * and structured multimodal content.
 *
 * Key changes from previous version:
 * - `sender` replaced with `role` to match backend naming
 * - Added `content` field for structured content blocks
 * - Maintained backward compatibility for simple text messages
 */
export interface Message {
  id: string;
  role: MessageRole;              // ✨ Unified field name (was: sender)
  text: string;                    // Simple text content (compatibility)
  content?: ContentBlock[];        // Structured content blocks (multimodal)
  files?: FileData[];
  timestamp: number;
  streaming?: boolean;             // Marks if text is streaming
  status?: MessageStatus;          // User message status
  isLoading?: boolean;             // Marks loading state
  isRead?: boolean;                // Marks if user message was read
  newText?: string;                // New text portion for streaming
  onRenderComplete?: () => void;   // Render completion callback
  usage?: TokenUsage;              // Token usage statistics (for assistant messages)
}

// =====================
// Supporting Types
// =====================

/**
 * Message status enumeration.
 *
 * Tracks the lifecycle of a user message from creation to API processing.
 */
export enum MessageStatus {
  SENDING = 'sending', // Being sent to backend
  SENT = 'sent',       // Successfully sent to backend
  READ = 'read',       // Passed to LLM API by backend
  ERROR = 'error'      // Sending failed
}

/**
 * File attachment data.
 *
 * Represents files uploaded with user messages.
 */
export interface FileData {
  name: string;
  type: string;
  data: string;                    // Base64-encoded file data
}

// =====================
// Chat Context Types
// =====================

/**
 * Chat state interface.
 *
 * Represents the current state of the chat session.
 */
export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  isLLMThinking: boolean;  // Global LLM thinking status (includes text streaming and tool preparation)
}

/**
 * Chat context type.
 *
 * Defines the complete chat context API available to components.
 */
export interface ChatContextType extends ChatState {
  sendMessage: (text: string, files?: FileData[], mentionedFiles?: string[]) => Promise<void>;
  clearChat: () => void;
  deleteMessage: (messageId: string) => Promise<void>;
  addVideoMessage: (videoPath: string, content?: string) => string;
}
