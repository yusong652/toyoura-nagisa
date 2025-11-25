/**
 * CLI UI Type Definitions
 * Reference: Gemini CLI ui/types.ts
 */

import type { ReactNode } from 'react';

// Message types for history display
export enum MessageType {
  USER = 'user',
  ASSISTANT = 'assistant',
  TOOL_CALL = 'tool_call',
  TOOL_RESULT = 'tool_result',
  THINKING = 'thinking',
  ERROR = 'error',
  INFO = 'info',
  CHAT_LIST = 'chat_list',
}

// Content block types
export interface TextBlock {
  type: 'text';
  text: string;
}

export interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
}

export interface ToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: string;
  is_error?: boolean;
}

export type ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock;

// History item types
export interface HistoryItemBase {
  id: string;
  timestamp: number;
}

export interface UserHistoryItem extends HistoryItemBase {
  type: MessageType.USER;
  text: string;
}

export interface AssistantHistoryItem extends HistoryItemBase {
  type: MessageType.ASSISTANT;
  content: ContentBlock[];
  isStreaming?: boolean;
}

export interface ThinkingHistoryItem extends HistoryItemBase {
  type: MessageType.THINKING;
  thinking: string;
  isExpanded?: boolean;
}

export interface ToolCallHistoryItem extends HistoryItemBase {
  type: MessageType.TOOL_CALL;
  toolName: string;
  toolInput: Record<string, unknown>;
  toolCallId: string;
}

export interface ToolResultHistoryItem extends HistoryItemBase {
  type: MessageType.TOOL_RESULT;
  toolCallId: string;
  content: string;
  isError?: boolean;
}

export interface ErrorHistoryItem extends HistoryItemBase {
  type: MessageType.ERROR;
  message: string;
}

export interface InfoHistoryItem extends HistoryItemBase {
  type: MessageType.INFO;
  message: string;
}

export type HistoryItem =
  | UserHistoryItem
  | AssistantHistoryItem
  | ThinkingHistoryItem
  | ToolCallHistoryItem
  | ToolResultHistoryItem
  | ErrorHistoryItem
  | InfoHistoryItem;

// HistoryItemWithoutId omits both 'id' and 'timestamp' as they are auto-generated
export type HistoryItemWithoutId = Omit<HistoryItem, 'id' | 'timestamp'> & {
  timestamp?: number;
};

// Tool confirmation types
export interface ToolConfirmationData {
  tool_call_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  description?: string;
  command?: string;
}

export interface ConfirmationRequest {
  id: string;
  data: ToolConfirmationData;
  resolve: (approved: boolean, message?: string) => void;
}

// Session types
export interface SessionInfo {
  id: string;
  name: string;
  createdAt: string;
  messageCount: number;
}

export interface SessionStats {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
}

// Connection status
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// Dialog types
export type DialogType = 'help' | 'profile' | 'session' | 'settings';

// App state
export interface AppState {
  isStreaming: boolean;
  currentSessionId: string | null;
  connectionStatus: ConnectionStatus;
  pendingConfirmation: ToolConfirmationData | null;
}
