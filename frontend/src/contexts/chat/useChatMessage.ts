/**
 * useChatMessage Hook
 *
 * Manages complete chat message functionality
 * - Message state management (messages, setMessages)
 * - Send messages (including creating user and bot messages)
 * - Session history loading and conversion
 * - Delete messages
 * - Clear chat
 * - Message status updates
 */

import { useState, useCallback, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, MessageStatus, FileData } from '../../types/chat'
import { sessionService, chatService } from '../../services/api'
import { useWebSocketMessageStatus } from '../../hooks/useWebSocketMessageStatus'

export interface UseChatMessageOptions {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  ttsEnabled?: boolean
  currentProfile?: string
  memoryEnabled?: boolean
}

export interface UseChatMessageReturn {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  deleteMessage: (messageId: string) => Promise<void>
  clearChat: () => void
  sendMessage: (text: string, files?: FileData[]) => Promise<{
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
  ttsEnabled = false,
  currentProfile = "general",
  memoryEnabled = true
}: UseChatMessageOptions): UseChatMessageReturn => {
  const [messages, setMessages] = useState<Message[]>([])

  // Reload messages when session changes
  useEffect(() => {
    if (currentSessionId) {
      // Directly call internal message loading logic instead of using switchSession wrapper
      const loadMessages = async () => {
        try {
          const historyData = await sessionService.getSessionHistory(currentSessionId)
          if (historyData.history && Array.isArray(historyData.history)) {
            const convertedMessages: Message[] = historyData.history
              .filter((msg: any) => {
                // Include all user, assistant, image, and video messages
                // Tool results within user messages will be rendered as content blocks
                return msg.role === 'user' ||
                       msg.role === 'assistant' ||
                       msg.role === 'image' ||
                       msg.role === 'video'
              })
              .map((msg: any): Message | null => {
                // ✨ Directly use backend role without mapping
                const role = msg.role
                if (!['user', 'assistant', 'image', 'video'].includes(role)) {
                  return null
                }

                let text = ''
                let files: any[] = []
                let content = msg.content  // ✨ Preserve structured content

                if (role === 'image') {
                  text = msg.content || ''
                  files.push({
                    name: 'generated_image',
                    type: 'image/png',
                    data: `/api/images/${msg.image_path}`
                  })
                } else if (role === 'video') {
                  text = msg.content || ''
                  // Determine video type based on file extension
                  const videoPath = msg.video_path
                  // Extract filename from path (format: session_id/filename.ext)
                  const filename = videoPath?.split('/').pop() || 'video.mp4'
                  const extension = filename.toLowerCase().split('.').pop()
                  let mediaType = 'video/mp4' // default
                  
                  if (extension === 'gif') {
                    mediaType = 'image/gif'
                  } else if (extension === 'webm') {
                    mediaType = 'video/webm'
                  } else if (extension === 'mp4') {
                    mediaType = 'video/mp4'
                  }
                  
                  files.push({
                    name: filename,
                    type: mediaType,
                    data: `/api/videos/${msg.video_path}`
                  })
                } else if (typeof msg.content === 'string') {
                  text = msg.content
                  // Add placeholder if assistant message is empty (may only have emotion)
                  if (role === 'assistant' && !text) {
                    text = '...'  // Use ellipsis as placeholder to indicate emotion-only action
                  }
                } else if (Array.isArray(msg.content)) {
                  // Process content array, compatible with both direct text and type fields

                  // Check if this is a structured message (tool_use, tool_result, thinking)
                  const hasStructuredBlocks = msg.content.some((item: any) =>
                    item.type === 'tool_use' ||
                    item.type === 'tool_result' ||
                    item.type === 'thinking'
                  )

                  // If it has structured blocks, preserve the content array
                  if (hasStructuredBlocks) {
                    // Don't clear content - it will be preserved below
                  } else {
                    // For simple text-only content arrays, extract text and clear content
                    content = undefined
                  }

                  const textContents = msg.content
                    .filter((item: any) => {
                      // Compatible with two formats: direct text field, or type is text
                      return item.text || (item.type === 'text' && item.text)
                    })
                    .map((item: any) => item.text)

                  let rawText = textContents.join('\n')

                  // Parse and process [[keyword]] markers
                  if (role === 'assistant') {
                    const keywordMatch = rawText.match(/\[\[(\w+)\]\]/);
                    if (keywordMatch) {
                      // Remove keyword marker
                      const textWithoutKeyword = rawText.replace(/\[\[\w+\]\]/g, '').trim();

                      if (!textWithoutKeyword) {
                        // Only keyword, show placeholder
                        text = '...';
                      } else {
                        // Has keyword and text, only show text
                        text = textWithoutKeyword;
                      }
                    } else {
                      // No keyword marker
                      text = rawText;

                      // Fallback: if assistant message is empty, add placeholder
                      if (!text.trim()) {
                        text = '...';
                      }
                    }
                  } else {
                    // For non-assistant messages, use original text directly
                    text = rawText;
                  }

                  msg.content.forEach((item: any) => {
                    if (item.inline_data) {
                      files.push({
                        name: `image_${files.length + 1}`,
                        type: item.inline_data.mime_type,
                        data: `data:${item.inline_data.mime_type};base64,${item.inline_data.data}`
                      })
                    }
                  })
                }

                return {
                  id: msg.id || uuidv4(),
                  role,  // ✨ Use role directly (was: sender)
                  text,
                  content: Array.isArray(content) ? content : undefined,  // ✨ Preserve structured content
                  files: files.length > 0 ? files : undefined,
                  timestamp: new Date(msg.timestamp || Date.now()).getTime(),
                  status: role === 'user' ? MessageStatus.READ : undefined,  // ✨ Check role instead of sender
                  streaming: false,
                  isLoading: false,
                  isRead: true,
                  toolState: msg.tool_state ? {
                    isUsingTool: msg.tool_state.is_using_tool || false,
                    toolNames: msg.tool_state.tool_name ? [msg.tool_state.tool_name] : undefined,
                    action: msg.tool_state.action
                  } : undefined
                }
              })
              .filter((msg: Message | null): msg is Message => msg !== null)
            setMessages(convertedMessages)
          } else {
            setMessages([])
          }
        } catch (error) {
          console.error('Failed to load session messages:', error)
          setMessages([])
        }
      }
      loadMessages()
    } else {
      setMessages([])
    }
  }, [currentSessionId])

  // Delete message
  const deleteMessage = useCallback(async (messageId: string): Promise<void> => {
    // Ensure there is a current session ID
    if (!currentSessionId) {
      throw new Error("No active session");
    }

    try {
      // First check if message exists in current message list
      const messageExists = messages.some(msg => msg.id === messageId);
      if (!messageExists) {
        console.error(`Message ${messageId} does not exist in current session`);
        throw new Error("Message does not exist in current session");
      }

      // First update message list in frontend, removing specified message
      setMessages(prev => prev.filter(msg => msg.id !== messageId));

      // Call backend API to delete message
      const responseData = await chatService.deleteMessage(currentSessionId, messageId);

      if (!responseData.success) {
        console.error('Failed to delete message:', responseData);

        // If backend deletion failed but frontend removed it, restore the deleted message
        await sessionSwitchSession(currentSessionId);
        throw new Error(`Failed to delete message: ${responseData.detail}`);
      }

      // Refresh session list after successful deletion
      await sessionRefreshSessions();
    } catch (error) {
      console.error('Failed to delete message:', error);
      throw error;
    }
  }, [currentSessionId, sessionRefreshSessions, messages, sessionSwitchSession]);

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


  // Base function for creating and sending messages
  // Responsibilities: Create user message -> Call backend API -> Create bot message placeholder
  // Does not include: Audio processing, streaming response handling, Live2D actions, etc.
  const sendMessage = useCallback(async (
    text: string,
    files: FileData[] = []
  ): Promise<{
    userMessageId: string
    botMessageId: string
    response: Response
  }> => {
    if (text.trim() === '' && files.length === 0) {
      throw new Error('Message content cannot be empty')
    }

    // Create user message
    const userMessageId = addUserMessage(text, files)

    try {
      // Create API request
      const sessionId = currentSessionId || localStorage.getItem('session_id') || "default_session"
      const response = await chatService.sendMessage(text, files, sessionId, userMessageId, currentProfile, ttsEnabled, memoryEnabled)

      return {
        userMessageId,
        botMessageId: '', // No longer need placeholder ID
        response
      }
    } catch (error) {
      // Update message to error status
      updateMessageStatus(userMessageId, MessageStatus.ERROR)
      throw error
    }
  }, [currentSessionId, currentProfile, ttsEnabled, memoryEnabled, addUserMessage, updateMessageStatus])

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