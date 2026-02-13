/**
 * Messaging module - Message processing and conversion utilities
 *
 * This module provides utilities for converting backend message formats
 * to frontend Message types using the Strategy pattern, as well as
 * stream and chunk processing for real-time message handling.
 */

// Message converters
export {
  MessageConverter,
  BackendMessage,
  ImageMessageConverter,
  VideoMessageConverter,
  UserMessageConverter,
  AssistantMessageConverter,
  MessageConverterManager,
  messageConverterManager
} from './MessageConverters.js';

// Stream processor
export {
  StreamProcessor,
  StreamEvent,
  StreamEventHandlers,
  StreamProcessorOptions
} from './StreamProcessor.js';

// Chunk processor
export {
  ChunkProcessor,
  ChunkData,
  MessageUpdateOptions,
  ChunkEventHandlers
} from './ChunkProcessor.js';

// Chat manager
export {
  ChatManager,
  ChatEvent,
  MessageCreatedPayload,
  MessageUpdatedPayload,
  MessageDeletedPayload,
  HistoryLoadedPayload,
  StreamStartedPayload,
  StreamCompletePayload,
  ErrorPayload,
  SendMessageOptions,
  SendMessageResult
} from './managers/ChatManager.js';
