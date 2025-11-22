/**
 * Message Manager - Core message state management
 * Handles message creation, updates, and streaming
 */

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: ContentBlock[]
  streaming?: boolean
  timestamp?: string
}

export interface ContentBlock {
  type: 'text' | 'thinking' | 'tool_use' | 'tool_result' | 'image'
  text?: string
  thinking?: string
  id?: string
  name?: string
  input?: any
  content?: any
  [key: string]: any
}

export class MessageManager {
  private messages: Map<string, Message> = new Map()
  private callbacks: Set<(messages: Message[]) => void> = new Set()

  /**
   * Create a new message
   */
  createMessage(id: string, role: 'user' | 'assistant' | 'system', initialContent: ContentBlock[] = []): Message {
    const message: Message = {
      id,
      role,
      content: initialContent,
      streaming: role === 'assistant',
      timestamp: new Date().toISOString()
    }

    this.messages.set(id, message)
    this.notifyChange()
    return message
  }

  /**
   * Update message content (for streaming updates)
   */
  updateMessage(id: string, content: ContentBlock[], streaming: boolean = true): void {
    const message = this.messages.get(id)
    if (message) {
      message.content = content
      message.streaming = streaming
      this.messages.set(id, message)
      this.notifyChange()
    }
  }

  /**
   * Finalize message (stop streaming)
   */
  finalizeMessage(id: string): void {
    const message = this.messages.get(id)
    if (message) {
      message.streaming = false
      this.messages.set(id, message)
      this.notifyChange()
    }
  }

  /**
   * Delete a message
   */
  deleteMessage(id: string): void {
    this.messages.delete(id)
    this.notifyChange()
  }

  /**
   * Get a single message
   */
  getMessage(id: string): Message | undefined {
    return this.messages.get(id)
  }

  /**
   * Get all messages
   */
  getAllMessages(): Message[] {
    return Array.from(this.messages.values()).sort((a, b) => {
      return new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime()
    })
  }

  /**
   * Clear all messages
   */
  clearMessages(): void {
    this.messages.clear()
    this.notifyChange()
  }

  /**
   * Subscribe to message changes
   */
  subscribe(callback: (messages: Message[]) => void): () => void {
    this.callbacks.add(callback)
    // Return unsubscribe function
    return () => {
      this.callbacks.delete(callback)
    }
  }

  /**
   * Notify all subscribers of changes
   */
  private notifyChange(): void {
    const messages = this.getAllMessages()
    this.callbacks.forEach(callback => callback(messages))
  }
}
