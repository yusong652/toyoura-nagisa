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

/**
 * Background process status representation.
 * Mirrors backend BackgroundProcess status for consistency.
 */
export interface BackgroundTask {
  process_id: string;                    // Unique 6-char identifier
  command: string;                       // Shell command
  description?: string;                  // Optional description
  status: 'running' | 'completed' | 'killed';

  // Output display (last 5 lines)
  recent_output: string[];               // Recent output lines
  has_more_output: boolean;              // More output available

  // Statistics
  runtime_seconds: number;               // Process runtime
  exit_code?: number;                    // Exit code when completed/killed

  // Metadata
  timestamp: string;                     // Last update timestamp
}

/**
 * Background process notification event from ConnectionManager.
 * Received when a background bash process starts, updates, or completes.
 */
export interface BackgroundProcessNotificationEvent {
  type: 'BACKGROUND_PROCESS_STARTED' |
        'BACKGROUND_PROCESS_OUTPUT_UPDATE' |
        'BACKGROUND_PROCESS_COMPLETED' |
        'BACKGROUND_PROCESS_KILLED';
  process_id: string;
  command: string;
  description?: string;
  status: 'running' | 'completed' | 'killed';
  recent_output: string[];
  has_more_output: boolean;
  runtime_seconds: number;
  exit_code?: number;
  session_id?: string;
  timestamp: string;
}
