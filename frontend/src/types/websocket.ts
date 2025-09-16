/**
 * WebSocket Message Type Definitions
 * Mirrors the Python backend WebSocket message models for type consistency
 */

export enum MessageType {
  // System messages
  CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED",
  CONNECTION_CLOSED = "CONNECTION_CLOSED",
  HEARTBEAT = "HEARTBEAT",
  HEARTBEAT_ACK = "HEARTBEAT_ACK",
  ERROR = "ERROR",
  
  // Chat messages
  CHAT_MESSAGE = "CHAT_MESSAGE",
  CHAT_RESPONSE = "CHAT_RESPONSE",
  CHAT_STREAM_START = "CHAT_STREAM_START",
  CHAT_STREAM_CHUNK = "CHAT_STREAM_CHUNK", 
  CHAT_STREAM_END = "CHAT_STREAM_END",
  STATUS_UPDATE = "STATUS_UPDATE",
  
  // Tool related
  NAGISA_IS_USING_TOOL = "NAGISA_IS_USING_TOOL",
  NAGISA_TOOL_USE_CONCLUDED = "NAGISA_TOOL_USE_CONCLUDED",
  TOOL_CALL_REQUEST = "TOOL_CALL_REQUEST",
  TOOL_CALL_RESULT = "TOOL_CALL_RESULT",
  
  // Title updates
  TITLE_UPDATE = "TITLE_UPDATE",
  
  // Location related
  LOCATION_REQUEST = "LOCATION_REQUEST", 
  LOCATION_RESPONSE = "LOCATION_RESPONSE",
  
  // TTS related
  TTS_CHUNK = "TTS_CHUNK",
  TTS_COMPLETE = "TTS_COMPLETE",

  // Message management
  MESSAGE_CREATE = "MESSAGE_CREATE",

  // Emotion and animation
  EMOTION_KEYWORD = "EMOTION_KEYWORD"
}

export interface BaseWebSocketMessage {
  type: MessageType;
  timestamp?: string;
  session_id?: string;
}

export interface ConnectionMessage extends BaseWebSocketMessage {
  type: MessageType.CONNECTION_ESTABLISHED | MessageType.CONNECTION_CLOSED;
  code?: number;
  reason?: string;
}

export interface HeartbeatMessage extends BaseWebSocketMessage {
  type: MessageType.HEARTBEAT | MessageType.HEARTBEAT_ACK;
}

export interface ErrorMessage extends BaseWebSocketMessage {
  type: MessageType.ERROR;
  error: string;
  details?: Record<string, any>;
  recoverable?: boolean;
}

export interface StatusMessage extends BaseWebSocketMessage {
  type: MessageType.STATUS_UPDATE;
  status: "sending" | "sent" | "read" | "error";
  message_id?: string;
  error_message?: string;  // Optional error details when status is "error"
}

export interface ToolUseMessage extends BaseWebSocketMessage {
  type: MessageType.NAGISA_IS_USING_TOOL | MessageType.NAGISA_TOOL_USE_CONCLUDED;
  tool_names?: string[];  // Array of tool names (new format)
  tool_name?: string;     // Legacy single tool name (backwards compatibility)
  action?: string;
  thinking?: string;      // LLM thinking content
  parameters?: Record<string, any>;
  results?: Record<string, any>;  // Results for concluded notifications
  result?: Record<string, any>;   // Legacy result field (backwards compatibility)
}

export interface TitleUpdateMessage extends BaseWebSocketMessage {
  type: MessageType.TITLE_UPDATE;
  payload: {
    session_id: string;
    title: string;
  };
}

export interface LocationRequestMessage extends BaseWebSocketMessage {
  type: MessageType.LOCATION_REQUEST;
  reason?: string;
  request_id?: string;
  accuracy_level?: string;
}

export interface LocationResponseMessage extends BaseWebSocketMessage {
  type: MessageType.LOCATION_RESPONSE;
  location_data?: Record<string, any>;
  error?: string;
}

export interface MessageCreateMessage extends BaseWebSocketMessage {
  type: MessageType.MESSAGE_CREATE;
  message_id: string;
  sender: string;
  initial_text?: string;
  streaming?: boolean;
}

export interface TTSChunkMessage extends BaseWebSocketMessage {
  type: MessageType.TTS_CHUNK;
  message_id?: string;  // Added message_id for association
  text: string;
  audio?: string;  // Base64 encoded audio data
  index: number;
  processing_time?: number;
  engine_status?: string;
  error?: string;
  is_final?: boolean;
}

// Keep legacy interface for compatibility
export interface TTSMessage extends BaseWebSocketMessage {
  type: MessageType.TTS_CHUNK | MessageType.TTS_COMPLETE;
  audio_url?: string;
  text?: string;
  chunk_index?: number;
  total_chunks?: number;
  index?: number; // For ordering
}

export interface ChatMessage extends BaseWebSocketMessage {
  type: MessageType.CHAT_MESSAGE | MessageType.CHAT_RESPONSE;
  content: string | Record<string, any> | any[];
  message_id: string;
  role: "user" | "assistant" | "system";
  keyword?: string;
  metadata?: Record<string, any>;
}

export interface EmotionKeywordMessage extends BaseWebSocketMessage {
  type: MessageType.EMOTION_KEYWORD;
  keyword: string;
  message_id?: string;
}

export type WebSocketMessage =
  | ConnectionMessage
  | HeartbeatMessage
  | ErrorMessage
  | StatusMessage
  | ToolUseMessage
  | TitleUpdateMessage
  | LocationRequestMessage
  | LocationResponseMessage
  | MessageCreateMessage
  | TTSChunkMessage
  | TTSMessage
  | ChatMessage
  | EmotionKeywordMessage;

// Message validation helpers
export function isValidMessageType(type: string): type is MessageType {
  return Object.values(MessageType).includes(type as MessageType);
}

export function validateWebSocketMessage(data: any): WebSocketMessage {
  if (!data || typeof data !== 'object') {
    throw new Error('Message must be an object');
  }
  
  if (!data.type || !isValidMessageType(data.type)) {
    throw new Error(`Invalid message type: ${data.type}`);
  }
  
  // Basic validation passed - TypeScript will handle the rest
  return data as WebSocketMessage;
}

// Message creation helpers
export function createErrorMessage(
  error: string,
  session_id?: string,
  details?: Record<string, any>,
  recoverable: boolean = true
): ErrorMessage {
  return {
    type: MessageType.ERROR,
    error,
    session_id,
    details,
    recoverable,
    timestamp: new Date().toISOString()
  };
}

export function createStatusMessage(
  status: "sending" | "sent" | "read" | "error",
  session_id?: string,
  message_id?: string,
  error_message?: string
): StatusMessage {
  return {
    type: MessageType.STATUS_UPDATE,
    status,
    session_id,
    message_id,
    error_message,
    timestamp: new Date().toISOString()
  };
}

export function createToolUseMessage(
  isUsing: boolean,
  tool_name?: string,
  parameters?: Record<string, any>,
  action?: string,
  result?: Record<string, any>,
  session_id?: string
): ToolUseMessage {
  return {
    type: isUsing ? MessageType.NAGISA_IS_USING_TOOL : MessageType.NAGISA_TOOL_USE_CONCLUDED,
    tool_name,
    parameters,
    action,
    result,
    session_id,
    timestamp: new Date().toISOString()
  };
}

// Legacy compatibility
export interface LegacyWebSocketMessage {
  type: string;
  [key: string]: any;
}

export function convertLegacyMessage(legacyMsg: LegacyWebSocketMessage): WebSocketMessage {
  try {
    return validateWebSocketMessage(legacyMsg);
  } catch (error) {
    // Return as generic message if validation fails
    return {
      type: MessageType.ERROR,
      error: `Legacy message conversion failed: ${error}`,
      details: { originalMessage: legacyMsg },
      timestamp: new Date().toISOString()
    };
  }
}

export default WebSocketMessage;