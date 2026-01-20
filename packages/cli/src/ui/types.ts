/**
 * CLI UI Type Definitions
 * Reference: Gemini CLI ui/types.ts
 */

// Message types for history display
export enum MessageType {
  USER = 'user',
  ASSISTANT = 'assistant',
  TOOL_CALL = 'tool_call',
  TOOL_RESULT = 'tool_result',
  ERROR = 'error',
  INFO = 'info',
  SHELL_COMMAND = 'shell_command',
  SHELL_RESULT = 'shell_result',
  PFC_CONSOLE_COMMAND = 'pfc_console_command',
  PFC_CONSOLE_RESULT = 'pfc_console_result',
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

/** SubAgent tool item for display (nested under invoke_agent) */
export interface SubagentToolItem {
  toolCallId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  hasResult?: boolean;  // True when tool execution completes
  isError?: boolean;    // True if tool execution resulted in error
}

export interface ToolCallHistoryItem extends HistoryItemBase {
  type: MessageType.TOOL_CALL;
  toolName: string;
  toolInput: Record<string, unknown>;
  toolCallId: string;
  isError?: boolean;    // True if the tool result was an error
  subagentTools?: SubagentToolItem[];  // SubAgent tools for invoke_agent
}

/** Diff information for file modification tools (edit, write) */
export interface DiffInfo {
  content: string;       // Unified diff content
  additions: number;     // Number of added lines
  deletions: number;     // Number of deleted lines
  file_path: string;     // Path to the modified file
}

/** File metadata for read tool results */
export interface FileInfo {
  path: string;          // Full file path
  type: 'text' | 'image' | 'binary';  // File type category
}

export interface ToolResultHistoryItem extends HistoryItemBase {
  type: MessageType.TOOL_RESULT;
  toolCallId: string;
  toolName?: string;     // Tool name for specialized display
  content: string;
  isError?: boolean;
  diff?: DiffInfo;       // Diff info for edit/write tools
  file?: FileInfo;       // File info for read tool
}

export interface ErrorHistoryItem extends HistoryItemBase {
  type: MessageType.ERROR;
  message: string;
}

export interface InfoHistoryItem extends HistoryItemBase {
  type: MessageType.INFO;
  message: string;
}

export interface ShellCommandHistoryItem extends HistoryItemBase {
  type: MessageType.SHELL_COMMAND;
  command: string;
}

export interface ShellResultHistoryItem extends HistoryItemBase {
  type: MessageType.SHELL_RESULT;
  stdout: string;
  stderr: string;
  exitCode: number;
  isError: boolean;
  backgrounded?: boolean;
  processId?: string;
}

export interface PfcConsoleCommandHistoryItem extends HistoryItemBase {
  type: MessageType.PFC_CONSOLE_COMMAND;
  code: string;
}

export interface PfcConsoleResultHistoryItem extends HistoryItemBase {
  type: MessageType.PFC_CONSOLE_RESULT;
  taskId: string | null;
  scriptName: string | null;
  output: string | null;
  result: unknown;
  elapsedTime: number | null;
  isError: boolean;
  error: string | null;
  connected: boolean;
}

export type HistoryItem =
  | UserHistoryItem
  | AssistantHistoryItem
  | ToolCallHistoryItem
  | ToolResultHistoryItem
  | ErrorHistoryItem
  | InfoHistoryItem
  | ShellCommandHistoryItem
  | ShellResultHistoryItem
  | PfcConsoleCommandHistoryItem
  | PfcConsoleResultHistoryItem;

// Separate types without id/timestamp for pending items
export interface UserHistoryItemWithoutId {
  type: MessageType.USER;
  text: string;
  timestamp?: number;
}

export interface AssistantHistoryItemWithoutId {
  type: MessageType.ASSISTANT;
  content: ContentBlock[];
  isStreaming?: boolean;
  timestamp?: number;
}

export interface ToolCallHistoryItemWithoutId {
  type: MessageType.TOOL_CALL;
  toolName: string;
  toolInput: Record<string, unknown>;
  toolCallId: string;
  timestamp?: number;
  hasResult?: boolean;  // True when tool result has been received
  isError?: boolean;    // True if the tool result was an error
  subagentTools?: SubagentToolItem[];  // SubAgent tools for invoke_agent
}

export interface ToolResultHistoryItemWithoutId {
  type: MessageType.TOOL_RESULT;
  toolCallId: string;
  toolName?: string;     // Tool name for specialized display
  content: string;
  isError?: boolean;
  diff?: DiffInfo;       // Diff info for edit/write tools
  file?: FileInfo;       // File info for read tool
  timestamp?: number;
}

export interface ErrorHistoryItemWithoutId {
  type: MessageType.ERROR;
  message: string;
  timestamp?: number;
}

export interface InfoHistoryItemWithoutId {
  type: MessageType.INFO;
  message: string;
  timestamp?: number;
}

export interface ShellCommandHistoryItemWithoutId {
  type: MessageType.SHELL_COMMAND;
  command: string;
  timestamp?: number;
}

export interface ShellResultHistoryItemWithoutId {
  type: MessageType.SHELL_RESULT;
  stdout: string;
  stderr: string;
  exitCode: number;
  isError: boolean;
  backgrounded?: boolean;
  processId?: string;
  timestamp?: number;
}

export interface PfcConsoleCommandHistoryItemWithoutId {
  type: MessageType.PFC_CONSOLE_COMMAND;
  code: string;
  timestamp?: number;
}

export interface PfcConsoleResultHistoryItemWithoutId {
  type: MessageType.PFC_CONSOLE_RESULT;
  taskId: string | null;
  scriptName: string | null;
  output: string | null;
  result: unknown;
  elapsedTime: number | null;
  isError: boolean;
  error: string | null;
  connected: boolean;
  timestamp?: number;
}

// HistoryItemWithoutId is a union of all item types without id
export type HistoryItemWithoutId =
  | UserHistoryItemWithoutId
  | AssistantHistoryItemWithoutId
  | ToolCallHistoryItemWithoutId
  | ToolResultHistoryItemWithoutId
  | ErrorHistoryItemWithoutId
  | InfoHistoryItemWithoutId
  | ShellCommandHistoryItemWithoutId
  | ShellResultHistoryItemWithoutId
  | PfcConsoleCommandHistoryItemWithoutId
  | PfcConsoleResultHistoryItemWithoutId;

// Tool confirmation types
export type ToolConfirmationType = 'edit' | 'exec' | 'info';

/** Base confirmation data shared by all confirmation types */
export interface BaseToolConfirmationData {
  tool_call_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  description?: string;
}

/** Confirmation for file edit operations (write, edit tools) */
export interface EditToolConfirmationData extends BaseToolConfirmationData {
  type: 'edit';
  /** Name of the file being modified */
  fileName: string;
  /** Full path to the file */
  filePath: string;
  /** Unified diff content showing the changes */
  fileDiff: string;
  /** Original file content (empty string for new files) */
  originalContent: string;
  /** New content to be written */
  newContent: string;
}

/** Confirmation for command execution (bash, shell tools) */
export interface ExecToolConfirmationData extends BaseToolConfirmationData {
  type: 'exec';
  /** The root command being executed */
  rootCommand: string;
  /** Full command string */
  command: string;
}

/** Generic confirmation for other tools */
export interface InfoToolConfirmationData extends BaseToolConfirmationData {
  type: 'info';
  /** Optional command string for display */
  command?: string;
}

/** Union type for all confirmation data types */
export type ToolConfirmationData =
  | EditToolConfirmationData
  | ExecToolConfirmationData
  | InfoToolConfirmationData;

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

// Agent profile types (matches backend AgentProfile enum)
export type AgentProfileType = 'pfc_expert' | 'disabled';

// Agent profile info from backend API
export interface AgentProfileInfo {
  profile_type: AgentProfileType;
  name: string;
  description: string;
  tool_count: number;
  estimated_tokens: number;
  color: string;
  icon: string;
}

// App state
export interface AppState {
  isStreaming: boolean;
  currentSessionId: string | null;
  connectionStatus: ConnectionStatus;
  pendingConfirmation: ToolConfirmationData | null;
}
