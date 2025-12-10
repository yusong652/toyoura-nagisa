/**
 * Stream Event Type Definitions
 * Extracted from useChatStream.ts for better modularity
 */

import type {
  ContentBlock,
  ToolCallHistoryItemWithoutId,
  ToolResultHistoryItemWithoutId,
  SubagentToolItem,
} from '../types.js';

// Re-export for convenience
export type { SubagentToolItem };

/**
 * Pending tool pair: tool call with its result (or placeholder)
 * Maintains order when tools execute/complete out of order
 */
export interface PendingToolPair {
  toolCallId: string;
  toolCall: ToolCallHistoryItemWithoutId;
  toolResult: ToolResultHistoryItemWithoutId | null; // null = waiting for result
  subagentTools?: SubagentToolItem[]; // SubAgent tools for invoke_agent (rendered below)
}

/**
 * Streaming update events from ConnectionManager
 */
export interface StreamingUpdateEvent {
  messageId: string;
  content: ContentBlock[];
  streaming: boolean;
  interrupted?: boolean; // True if streaming was interrupted by user (backend authority)
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    tokens_left: number;
  };
}

/**
 * Message create events from ConnectionManager
 */
export interface MessageCreateEvent {
  messageId: string;
  role: string;
  initialText: string;
  streaming: boolean;
}

/**
 * Tool confirmation events from ConnectionManager
 */
export interface ToolConfirmationEvent {
  message_id: string;
  tool_call_id: string;
  tool_name: string;
  command?: string;
  description?: string;
  // Fields for edit confirmation with diff display
  confirmation_type?: 'edit' | 'exec' | 'info';
  file_name?: string;
  file_path?: string;
  file_diff?: string;
  original_content?: string;
  new_content?: string;
}

/**
 * Tool result update events from ConnectionManager
 */
export interface ToolResultUpdateEvent {
  message_id: string;
  session_id: string;
  content: Array<{
    type: 'tool_result';
    tool_use_id: string;
    tool_name: string;
    content: any; // llm_content format from backend
    is_error: boolean;
    data?: {
      diff?: {
        content: string;
        additions: number;
        deletions: number;
        file_path: string;
      };
      [key: string]: any;
    };
  }>;
}

/**
 * SubAgent tool use notification from backend
 * Sent when a SubAgent (launched by invoke_agent) executes a tool
 */
export interface SubagentToolUseEvent {
  type: 'SUBAGENT_TOOL_USE';
  session_id: string;
  parent_tool_call_id: string;  // ID of the invoke_agent tool call
  tool_call_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

/**
 * SubAgent tool result notification from backend
 * Sent when a SubAgent tool completes execution
 */
export interface SubagentToolResultEvent {
  type: 'SUBAGENT_TOOL_RESULT';
  session_id: string;
  parent_tool_call_id: string;  // ID of the invoke_agent tool call
  tool_call_id: string;
  tool_name: string;
  is_error: boolean;
}
