/**
 * ChatManager - Platform-agnostic chat message coordination
 *
 * Orchestrates chat message lifecycle including sending, receiving, and processing.
 * Coordinates between multiple services (ChatService, SessionService) and processors
 * (StreamProcessor, ChunkProcessor, MessageConverter).
 *
 * Features:
 * - Message sending with file attachments
 * - Message history loading and conversion
 * - Message deletion
 * - Stream response coordination
 * - Event-driven architecture for UI updates
 */

import { EventEmitter } from '../../utils/EventEmitter.js'
import { ChatService } from '../../services/ChatService.js'
import { SessionService } from '../../services/SessionService.js'
import { MessageConverterManager, BackendMessage } from '../MessageConverters.js'
import { StreamProcessor, StreamEventHandlers } from '../StreamProcessor.js'
import { Message, FileData } from '../../types/messages.js'

/**
 * Event types emitted by ChatManager
 */
export enum ChatEvent {
  MESSAGE_CREATED = 'messageCreated',
  MESSAGE_UPDATED = 'messageUpdated',
  MESSAGE_DELETED = 'messageDeleted',
  HISTORY_LOADED = 'historyLoaded',
  STREAM_STARTED = 'streamStarted',
  STREAM_COMPLETE = 'streamComplete',
  ERROR = 'error'
}

/**
 * Event payload types
 */
export interface MessageCreatedPayload {
  message: Message
}

export interface MessageUpdatedPayload {
  messageId: string
  updates: Partial<Message>
}

export interface MessageDeletedPayload {
  messageId: string
}

export interface HistoryLoadedPayload {
  sessionId: string
  messages: Message[]
}

export interface StreamStartedPayload {
  userMessageId: string
  botMessageId: string
}

export interface StreamCompletePayload {
  botMessageId: string
}

export interface ErrorPayload {
  error: Error
  context?: string
}

/**
 * Options for sending a message
 */
export interface SendMessageOptions {
  sessionId: string
  mentionedFiles?: string[]
}

/**
 * Result of sending a message
 */
export interface SendMessageResult {
  userMessageId: string
  botMessageId: string
  response: Response
}

/**
 * ChatManager - Core chat orchestration logic
 *
 * Provides platform-agnostic chat management with event-based notifications.
 * Delegates API calls to services and coordinates stream processing.
 */
export class ChatManager extends EventEmitter {
  private chatService: ChatService
  private sessionService: SessionService
  private messageConverter: MessageConverterManager
  private streamProcessor: StreamProcessor | null = null

  /**
   * Create a new ChatManager
   *
   * @param chatService - Chat API service
   * @param sessionService - Session API service
   */
  constructor(chatService: ChatService, sessionService: SessionService) {
    super()
    this.chatService = chatService
    this.sessionService = sessionService
    this.messageConverter = new MessageConverterManager()
  }

  /**
   * Send a chat message
   *
   * Creates user message, sends to backend, and returns stream response.
   * Emits messageCreated event for user message.
   *
   * @param text - Message text
   * @param files - Optional file attachments
   * @param options - Send options (session, profile, etc.)
   * @returns Promise resolving to send result with response stream
   */
  async sendMessage(
    text: string,
    files: FileData[] = [],
    options: SendMessageOptions
  ): Promise<SendMessageResult> {
    try {
      // Validate input
      if (text.trim() === '' && files.length === 0) {
        throw new Error('Message content cannot be empty')
      }

      // Generate user message ID
      const userMessageId = this.generateMessageId()

      // Create user message
      const userMessage: Message = {
        id: userMessageId,
        role: 'user',
        text,
        files: files.length > 0 ? files : undefined,
        timestamp: Date.now(),
        status: 'sending' as any,
        streaming: false,
        isLoading: false,
        isRead: false
      }

      // Emit user message created event
      this.emit(ChatEvent.MESSAGE_CREATED, {
        message: userMessage
      } as MessageCreatedPayload)

      // Send message to backend
      const response = await this.chatService.sendMessage(
        text,
        files,
        options.sessionId,
        userMessageId,
        options.mentionedFiles || []
      )

      // Generate bot message ID (will be created via WebSocket MESSAGE_CREATE event)
      const botMessageId = ''

      // Emit stream started event
      this.emit(ChatEvent.STREAM_STARTED, {
        userMessageId,
        botMessageId
      } as StreamStartedPayload)

      return {
        userMessageId,
        botMessageId,
        response
      }
    } catch (error) {
      this.emit(ChatEvent.ERROR, {
        error: error as Error,
        context: 'sendMessage'
      } as ErrorPayload)
      throw error
    }
  }

  /**
   * Process stream response
   *
   * Processes SSE stream response using StreamProcessor.
   * Emits streamComplete event when done.
   *
   * @param response - Fetch Response with SSE stream
   * @param userMessageId - ID of user message
   * @param botMessageId - ID of bot message
   * @param handlers - Stream event handlers
   */
  async processStream(
    response: Response,
    userMessageId: string,
    botMessageId: string,
    handlers: StreamEventHandlers
  ): Promise<void> {
    try {
      // Create stream processor with handlers
      this.streamProcessor = new StreamProcessor({
        ...handlers,
        onStreamComplete: () => {
          this.emit(ChatEvent.STREAM_COMPLETE, {
            botMessageId
          } as StreamCompletePayload)
          handlers.onStreamComplete?.()
        }
      })

      // Process the stream
      await this.streamProcessor.processStream(response, {
        userMessageId,
        botMessageId
      })
    } catch (error) {
      this.emit(ChatEvent.ERROR, {
        error: error as Error,
        context: 'processStream'
      } as ErrorPayload)
      throw error
    }
  }

  /**
   * Load message history for a session
   *
   * Fetches and converts backend messages to frontend format.
   * Emits historyLoaded event with converted messages.
   *
   * @param sessionId - Session ID to load history for
   * @returns Promise resolving to array of messages
   */
  async loadHistory(sessionId: string): Promise<Message[]> {
    try {
      const historyData = await this.sessionService.getSessionHistory(sessionId)

      if (!historyData.history || !Array.isArray(historyData.history)) {
        return []
      }

      // Filter valid message roles
      const backendMessages = historyData.history.filter((msg: any) =>
        msg.role === 'user' ||
        msg.role === 'assistant' ||
        msg.role === 'image' ||
        msg.role === 'video'
      ) as BackendMessage[]

      // Convert messages
      const messages = this.messageConverter.convertMany(backendMessages)

      // Emit history loaded event
      this.emit(ChatEvent.HISTORY_LOADED, {
        sessionId,
        messages
      } as HistoryLoadedPayload)

      return messages
    } catch (error) {
      this.emit(ChatEvent.ERROR, {
        error: error as Error,
        context: 'loadHistory'
      } as ErrorPayload)
      throw error
    }
  }

  /**
   * Delete a message
   *
   * Deletes message from backend and emits messageDeleted event.
   *
   * @param messageId - ID of message to delete
   * @param sessionId - Current session ID
   */
  async deleteMessage(messageId: string, sessionId: string): Promise<void> {
    try {
      // HttpClient unwraps ApiResponse, so we get MessageDeleteData directly
      // If deletion fails, HttpClient throws ApiBusinessError
      await this.chatService.deleteMessage(sessionId, messageId)

      // Emit message deleted event
      this.emit(ChatEvent.MESSAGE_DELETED, {
        messageId
      } as MessageDeletedPayload)
    } catch (error) {
      this.emit(ChatEvent.ERROR, {
        error: error as Error,
        context: 'deleteMessage'
      } as ErrorPayload)
      throw error
    }
  }

  /**
   * Update a message
   *
   * Emits messageUpdated event with changes.
   * Note: This doesn't update backend, only emits event for UI update.
   *
   * @param messageId - ID of message to update
   * @param updates - Partial message updates
   */
  updateMessage(messageId: string, updates: Partial<Message>): void {
    this.emit(ChatEvent.MESSAGE_UPDATED, {
      messageId,
      updates
    } as MessageUpdatedPayload)
  }

  /**
   * Generate a unique message ID
   *
   * Uses crypto.randomUUID if available, otherwise falls back to timestamp-based ID.
   *
   * @returns Unique message ID
   */
  private generateMessageId(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
    // Fallback for environments without crypto.randomUUID
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}
