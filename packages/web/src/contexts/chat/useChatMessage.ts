/**
 * useChatMessage Hook
 *
 * React wrapper for ChatManager - manages message operations
 * - Message state management (messages, setMessages)
 * - Send messages via ChatManager
 * - Load history via ChatManager
 * - Delete messages via ChatManager
 * - Clear chat
 * - Message status updates
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { v4 as uuidv4 } from 'uuid'
import {
  Message,
  MessageStatus,
  FileData,
  ChatManager,
  ChatEvent,
  sessionService,
  chatService
} from '@toyoura-nagisa/core'
import { useWebSocketMessageStatus } from '../../hooks/useWebSocketMessageStatus'

export interface UseChatMessageOptions {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  currentProfile?: string
  memoryEnabled?: boolean
  setIsLLMThinking?: (thinking: boolean) => void  // Callback to update global LLM thinking status
}

export interface UseChatMessageReturn {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  deleteMessage: (messageId: string) => Promise<void>
  clearChat: () => void
  sendMessage: (text: string, files?: FileData[], mentionedFiles?: string[]) => Promise<{
    userMessageId: string
    botMessageId: string
    response: Response
  }>
  addUserMessage: (text: string, files?: FileData[]) => string
  addVideoMessage: (videoPath: string, content?: string) => string
  updateMessageStatus: (messageId: string, status: MessageStatus) => void
  updateBotMessage: (messageId: string, updates: Partial<Message>) => void
}

export const useChatMessage = ({
  currentSessionId,
  sessionRefreshSessions,
  sessionSwitchSession,
  currentProfile = "pfc",
  memoryEnabled = true,
  setIsLLMThinking
}: UseChatMessageOptions): UseChatMessageReturn => {
  const [messages, setMessages] = useState<Message[]>([])

  // Create ChatManager instance (lazy initialization)
  const chatManagerRef = useRef<ChatManager | null>(null)
  if (!chatManagerRef.current) {
    chatManagerRef.current = new ChatManager(chatService, sessionService)
  }
  const chatManager = chatManagerRef.current

  // Subscribe to ChatManager events
  useEffect(() => {
    // Message created event
    chatManager.on(ChatEvent.MESSAGE_CREATED, ({ message }) => {
      setMessages(prev => [...prev, message])
    })

    // Message updated event
    chatManager.on(ChatEvent.MESSAGE_UPDATED, ({ messageId, updates }) => {
      setMessages(prev =>
        prev.map(msg => (msg.id === messageId ? { ...msg, ...updates } : msg))
      )
    })

    // Message deleted event
    chatManager.on(ChatEvent.MESSAGE_DELETED, ({ messageId }) => {
      setMessages(prev => prev.filter(msg => msg.id !== messageId))
    })

    // History loaded event
    chatManager.on(ChatEvent.HISTORY_LOADED, ({ messages: loadedMessages }) => {
      setMessages(loadedMessages)
    })

    return () => {
      chatManager.removeAllListeners()
    }
  }, [chatManager])

  // Reload messages when session changes using ChatManager
  useEffect(() => {
    if (currentSessionId) {
      const loadMessages = async () => {
        try {
          await chatManager.loadHistory(currentSessionId)
        } catch (error) {
          console.error('Failed to load session messages:', error)
          setMessages([])
        }
      }
      loadMessages()
    } else {
      setMessages([])
    }
  }, [currentSessionId, chatManager])

  // Delete message via ChatManager
  const deleteMessage = useCallback(async (messageId: string): Promise<void> => {
    if (!currentSessionId) {
      throw new Error("No active session")
    }

    try {
      // Check if message exists
      const messageExists = messages.some(msg => msg.id === messageId)
      if (!messageExists) {
        console.error(`Message ${messageId} does not exist in current session`)
        throw new Error("Message does not exist in current session")
      }

      // Delete via ChatManager (will emit MESSAGE_DELETED event)
      await chatManager.deleteMessage(messageId, currentSessionId)

      // Refresh session list after successful deletion
      await sessionRefreshSessions()
    } catch (error) {
      console.error('Failed to delete message:', error)
      // Restore messages by reloading from backend
      await sessionSwitchSession(currentSessionId)
      throw error
    }
  }, [currentSessionId, chatManager, messages, sessionRefreshSessions, sessionSwitchSession])

  // Clear chat
  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  // Add user message
  const addUserMessage = useCallback((text: string, files: FileData[] = []): string => {
    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',  // ✨ Use role instead of sender
      text,
      files: files.length > 0 ? files : undefined,
      timestamp: Date.now(),
      status: MessageStatus.SENDING
    }

    setMessages(prev => [...prev, userMessage])
    return userMessage.id
  }, [])


  // Add video message
  const addVideoMessage = useCallback((videoPath: string, content: string = "") => {
    const videoMessageId = uuidv4()
    // Extract filename from path (format: session_id/filename.ext)
    const filename = videoPath.split('/').pop() || 'video.mp4'
    const extension = filename.toLowerCase().split('.').pop()
    let mediaType = 'video/mp4' // default

    if (extension === 'gif') {
      mediaType = 'image/gif'
    } else if (extension === 'webm') {
      mediaType = 'video/webm'
    } else if (extension === 'mp4') {
      mediaType = 'video/mp4'
    }

    const videoMessage: Message = {
      id: videoMessageId,
      role: 'assistant',  // ✨ Use role instead of sender: 'bot'
      text: content, // Empty content, only show video
      files: [{
        name: filename,
        type: mediaType,
        data: `/api/videos/${videoPath}`
      }],
      timestamp: Date.now()
    }

    setMessages(prev => [...prev, videoMessage])
    return videoMessageId
  }, [])

  // Update message status
  const updateMessageStatus = useCallback((messageId: string, status: MessageStatus, errorMessage?: string) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === messageId
          ? { ...msg, status, errorMessage }
          : msg
      )
    )
  }, [])
  
  // Subscribe to WebSocket message status updates
  useWebSocketMessageStatus({
    onStatusUpdate: updateMessageStatus
  })

  // Subscribe to WebSocket message creation events
  useEffect(() => {
    const handleMessageCreate = (event: Event) => {
      const customEvent = event as CustomEvent
      const { messageId, role, initialText, streaming } = customEvent.detail

      // Only create assistant messages
      if (role === 'assistant') {
        // Set global LLM thinking status (LLM started working)
        setIsLLMThinking?.(true)

        // Create new assistant message with specified ID
        const newBotMessage: Message = {
          id: messageId,
          role: 'assistant',
          text: initialText,
          timestamp: Date.now(),
          streaming: streaming,
          isLoading: false,
          isRead: false
        }

        setMessages(prev => [...prev, newBotMessage])
      }
    }

    window.addEventListener('messageCreate', handleMessageCreate)

    return () => {
      window.removeEventListener('messageCreate', handleMessageCreate)
    }
  }, [setIsLLMThinking])

  // Subscribe to tool result update events for real-time display
  // Follows CLI pattern: use tool_use_id to match tool_call and tool_result
  useEffect(() => {
    const handleToolResultUpdate = (event: Event) => {
      const customEvent = event as CustomEvent
      const { content } = customEvent.detail

      if (!content || !Array.isArray(content)) return

      // Extract tool_use_id from content blocks (like CLI does)
      for (const block of content) {
        if (block.type !== 'tool_result') continue

        const toolUseId = block.tool_use_id
        if (!toolUseId) continue

        // Get llm_content for the tool result content block
        const llmContent = block.content

        // Create tool result content block matching frontend expected format
        const toolResultContent = {
          type: 'tool_result' as const,
          tool_use_id: toolUseId,
          tool_name: block.tool_name || 'unknown',
          content: llmContent,  // Keep original llm_content structure
          is_error: block.is_error || false
        }

        // Create a new message for the tool result
        // Use tool_use_id as key for deduplication (like CLI)
        const toolResultMessageId = `tool_result_${toolUseId}`
        const newMessage: Message = {
          id: toolResultMessageId,
          role: 'user',  // tool_result is stored as user message
          text: '',
          content: [toolResultContent],
          timestamp: Date.now(),
          streaming: false
        }

        setMessages(prev => {
          // Check if this tool result already exists (by tool_use_id)
          const exists = prev.some(msg =>
            msg.content?.some((b: any) =>
              b.type === 'tool_result' && b.tool_use_id === toolUseId
            )
          )
          if (exists) {
            return prev
          }
          return [...prev, newMessage]
        })
      }
    }

    window.addEventListener('toolResultUpdate', handleToolResultUpdate)

    return () => {
      window.removeEventListener('toolResultUpdate', handleToolResultUpdate)
    }
  }, [])

  // Update bot message
  const updateBotMessage = useCallback((messageId: string, updates: Partial<Message>) => {
    setMessages(prev => {
      const updatedMessages = prev.map(msg => {
        if (msg.id === messageId) {
          const updatedMsg = { ...msg, ...updates }
          // If update includes new ID, ensure message integrity is maintained
          if (updates.id && updates.id !== messageId) {
            console.log(`[updateBotMessage] Updating message ID: ${messageId} -> ${updates.id}`)
          }
          return updatedMsg
        }
        return msg
      })

      // Verify message exists
      const messageFound = updatedMessages.some(msg =>
        msg.id === messageId || (updates.id && msg.id === updates.id)
      )
      if (!messageFound) {
        console.warn(`[updateBotMessage] Warning: Message with ID ${messageId} not found`)
      }

      return updatedMessages
    })
  }, [])


  // Send message via ChatManager
  // Returns response stream for further processing (SSE metadata, etc.)
  const sendMessage = useCallback(async (
    text: string,
    files: FileData[] = [],
    mentionedFiles: string[] = []
  ): Promise<{
    userMessageId: string
    botMessageId: string
    response: Response
  }> => {
    try {
      const sessionId = currentSessionId || localStorage.getItem('session_id') || "default_session"

      // Send message via ChatManager
      const result = await chatManager.sendMessage(text, files, {
        sessionId,
        profile: currentProfile,
        memoryEnabled,
        mentionedFiles
      })

      return result
    } catch (error) {
      console.error('Failed to send message:', error)
      throw error
    }
  }, [currentSessionId, currentProfile, memoryEnabled, chatManager])

  return {
    messages,
    setMessages,
    deleteMessage,
    clearChat,
    sendMessage,
    addUserMessage,
    addVideoMessage,
    updateMessageStatus,
    updateBotMessage
  }
}
