/**
 * Message Converter Strategy Pattern
 *
 * Converts backend message formats to frontend Message types.
 * Each converter handles a specific message role type.
 */

import { v4 as uuidv4 } from 'uuid'
import { Message, MessageStatus, ContentBlock } from '../../types/chat'

// =====================
// Backend Message Types
// =====================

/**
 * Backend message structure from session history API
 */
export interface BackendMessage {
  id?: string
  role: 'user' | 'assistant' | 'image' | 'video'
  content: string | BackendContentBlock[]
  image_path?: string
  video_path?: string
  timestamp?: string
}

// =====================
// Additional Content Block Types
// =====================

/**
 * Inline image data block (used for user-uploaded images).
 *
 * This type represents inline base64 image data sent from the backend
 * when users upload images. It's not part of the standard ContentBlock union
 * but may appear in backend message content arrays.
 *
 * Note: This is different from role: 'image' messages, which are for
 * AI-generated images and don't participate in LLM context.
 */
interface InlineImageBlock {
  inline_data: {
    mime_type: string
    data: string  // base64 encoded
  }
}

/**
 * Backend content block union (includes inline images)
 */
type BackendContentBlock = ContentBlock | InlineImageBlock

// =====================
// Type Guards
// =====================

/**
 * Checks if content block is a text block with text content
 * Supports both new format {"type": "text", "text": "..."} and legacy format {"text": "..."}
 */
function isTextBlock(block: BackendContentBlock): block is ContentBlock & { type: 'text'; text: string } {
  // New format with explicit type field
  if ('type' in block && block.type === 'text' && 'text' in block && typeof block.text === 'string') {
    return true
  }
  // Legacy format without type field (backward compatibility)
  if (!('type' in block) && 'text' in block && typeof block.text === 'string') {
    return true
  }
  return false
}

/**
 * Checks if content block has inline image data
 */
function isInlineImageBlock(block: BackendContentBlock): block is InlineImageBlock {
  return (
    typeof block === 'object' &&
    block !== null &&
    'inline_data' in block &&
    typeof block.inline_data === 'object' &&
    block.inline_data !== null &&
    'mime_type' in block.inline_data &&
    'data' in block.inline_data
  )
}

/**
 * Checks if content array has structured blocks (tool_use, tool_result, thinking)
 */
function hasStructuredBlocks(content: ContentBlock[]): boolean {
  return content.some(block =>
    block.type === 'tool_use' ||
    block.type === 'tool_result' ||
    block.type === 'thinking'
  )
}

// =====================
// Converter Interface
// =====================

/**
 * Message converter strategy interface
 */
export interface MessageConverter {
  /**
   * Check if this converter can handle the given message
   */
  canHandle(msg: BackendMessage): boolean

  /**
   * Convert backend message to frontend Message type
   */
  convert(msg: BackendMessage): Message
}

// =====================
// Converter Implementations
// =====================

/**
 * Converts image messages from backend to frontend format
 */
export class ImageMessageConverter implements MessageConverter {
  canHandle(msg: BackendMessage): boolean {
    return msg.role === 'image'
  }

  convert(msg: BackendMessage): Message {
    const text = typeof msg.content === 'string' ? msg.content : ''

    return {
      id: msg.id || uuidv4(),
      role: 'image',
      text,
      files: [{
        name: 'generated_image',
        type: 'image/png',
        data: `/api/images/${msg.image_path}`
      }],
      timestamp: new Date(msg.timestamp || Date.now()).getTime(),
      status: undefined,
      streaming: false,
      isLoading: false,
      isRead: true
    }
  }
}

/**
 * Converts video messages from backend to frontend format
 */
export class VideoMessageConverter implements MessageConverter {
  canHandle(msg: BackendMessage): boolean {
    return msg.role === 'video'
  }

  convert(msg: BackendMessage): Message {
    const text = typeof msg.content === 'string' ? msg.content : ''
    const videoPath = msg.video_path || ''
    const filename = videoPath.split('/').pop() || 'video.mp4'
    const mediaType = this.getMediaType(filename)

    return {
      id: msg.id || uuidv4(),
      role: 'video',
      text,
      files: [{
        name: filename,
        type: mediaType,
        data: `/api/videos/${videoPath}`
      }],
      timestamp: new Date(msg.timestamp || Date.now()).getTime(),
      status: undefined,
      streaming: false,
      isLoading: false,
      isRead: true
    }
  }

  private getMediaType(filename: string): string {
    const extension = filename.toLowerCase().split('.').pop()
    const typeMap: Record<string, string> = {
      'gif': 'image/gif',
      'webm': 'video/webm',
      'mp4': 'video/mp4'
    }
    return typeMap[extension || 'mp4'] || 'video/mp4'
  }
}

/**
 * Converts user messages from backend to frontend format
 */
export class UserMessageConverter implements MessageConverter {
  canHandle(msg: BackendMessage): boolean {
    return msg.role === 'user'
  }

  convert(msg: BackendMessage): Message {
    const { text, content, files } = this.extractContent(msg.content)

    return {
      id: msg.id || uuidv4(),
      role: 'user',
      text,
      content,
      files: files.length > 0 ? files : undefined,
      timestamp: new Date(msg.timestamp || Date.now()).getTime(),
      status: MessageStatus.READ,
      streaming: false,
      isLoading: false,
      isRead: true
    }
  }

  private extractContent(content: string | BackendContentBlock[]): {
    text: string
    content: ContentBlock[] | undefined
    files: any[]
  } {
    if (typeof content === 'string') {
      return { text: content, content: undefined, files: [] }
    }

    if (!Array.isArray(content)) {
      return { text: '', content: undefined, files: [] }
    }

    // Check if this is a structured message (tool_use, tool_result, thinking)
    // Only preserve standard ContentBlock types
    const structuredBlocks = content.filter((block): block is ContentBlock =>
      'type' in block && (
        block.type === 'tool_use' ||
        block.type === 'tool_result' ||
        block.type === 'thinking' ||
        block.type === 'text'
      )
    )
    const hasStructured = hasStructuredBlocks(structuredBlocks)
    const preservedContent = hasStructured ? structuredBlocks : undefined

    // Extract text from content blocks
    const textContents = content
      .filter(isTextBlock)
      .map(block => block.text)

    const text = textContents.join('\n')

    // Extract inline image data
    const files = content
      .filter(isInlineImageBlock)
      .map((block, index) => ({
        name: `image_${index + 1}`,
        type: block.inline_data.mime_type,
        data: `data:${block.inline_data.mime_type};base64,${block.inline_data.data}`
      }))

    return { text, content: preservedContent, files }
  }
}

/**
 * Converts assistant messages from backend to frontend format
 */
export class AssistantMessageConverter implements MessageConverter {
  canHandle(msg: BackendMessage): boolean {
    return msg.role === 'assistant'
  }

  convert(msg: BackendMessage): Message {
    const { text, content, files } = this.extractContent(msg.content)

    return {
      id: msg.id || uuidv4(),
      role: 'assistant',
      text,
      content,
      files: files.length > 0 ? files : undefined,
      timestamp: new Date(msg.timestamp || Date.now()).getTime(),
      status: undefined,
      streaming: false,
      isLoading: false,
      isRead: true
    }
  }

  private extractContent(content: string | BackendContentBlock[]): {
    text: string
    content: ContentBlock[] | undefined
    files: any[]
  } {
    if (typeof content === 'string') {
      const processedText = this.processKeywordMarkers(content)
      return { text: processedText, content: undefined, files: [] }
    }

    if (!Array.isArray(content)) {
      return { text: '...', content: undefined, files: [] }
    }

    // Check if this is a structured message (tool_use, tool_result, thinking)
    // Only preserve standard ContentBlock types
    const structuredBlocks = content.filter((block): block is ContentBlock =>
      'type' in block && (
        block.type === 'tool_use' ||
        block.type === 'tool_result' ||
        block.type === 'thinking' ||
        block.type === 'text'
      )
    )
    const hasStructured = hasStructuredBlocks(structuredBlocks)
    const preservedContent = hasStructured ? structuredBlocks : undefined

    // Extract text from content blocks
    const textContents = content
      .filter(isTextBlock)
      .map(block => block.text)

    const rawText = textContents.join('\n')
    const processedText = this.processKeywordMarkers(rawText)

    // Extract inline image data
    const files = content
      .filter(isInlineImageBlock)
      .map((block, index) => ({
        name: `image_${index + 1}`,
        type: block.inline_data.mime_type,
        data: `data:${block.inline_data.mime_type};base64,${block.inline_data.data}`
      }))

    return { text: processedText, content: preservedContent, files }
  }

  /**
   * Process [[keyword]] markers in assistant messages
   *
   * Removes emotion keywords and shows placeholder if no text remains
   */
  private processKeywordMarkers(rawText: string): string {
    const keywordMatch = rawText.match(/\[\[(\w+)\]\]/)

    if (keywordMatch) {
      // Remove keyword marker
      const textWithoutKeyword = rawText.replace(/\[\[\w+\]\]/g, '').trim()

      if (!textWithoutKeyword) {
        // Only keyword, show placeholder
        return '...'
      } else {
        // Has keyword and text, only show text
        return textWithoutKeyword
      }
    }

    // No keyword marker - use original text
    const trimmedText = rawText.trim()

    // Fallback: if assistant message is empty, add placeholder
    if (!trimmedText) {
      return '...'
    }

    return trimmedText
  }
}

// =====================
// Converter Manager
// =====================

/**
 * Manages message conversion using strategy pattern
 *
 * Automatically selects the appropriate converter based on message role
 */
export class MessageConverterManager {
  private converters: MessageConverter[]

  constructor() {
    this.converters = [
      new ImageMessageConverter(),
      new VideoMessageConverter(),
      new UserMessageConverter(),
      new AssistantMessageConverter()
    ]
  }

  /**
   * Convert a backend message to frontend Message type
   *
   * @param msg - Backend message from session history
   * @returns Converted Message or null if no converter matches
   */
  convert(msg: BackendMessage): Message | null {
    const converter = this.converters.find(c => c.canHandle(msg))

    if (!converter) {
      console.warn(`No converter found for message role: ${msg.role}`, msg)
      return null
    }

    return converter.convert(msg)
  }

  /**
   * Convert an array of backend messages to frontend Messages
   *
   * @param messages - Array of backend messages
   * @returns Array of converted Messages (filtered for successful conversions)
   */
  convertMany(messages: BackendMessage[]): Message[] {
    return messages
      .map(msg => this.convert(msg))
      .filter((msg): msg is Message => msg !== null)
  }
}

/**
 * Singleton instance of the message converter manager
 */
export const messageConverterManager = new MessageConverterManager()
