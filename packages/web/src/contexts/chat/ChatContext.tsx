import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { FileData, ChatContextType} from '@toyoura-nagisa/core'
import { useSession } from '../session/SessionContext'
import { useMemory } from '../MemoryContext'
import { useChatMessage } from './useChatMessage'
import { useStreamHandler } from './useStreamHandler'
import { useStreamingUpdateHandler } from './useStreamingUpdateHandler'

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export const useChat = (): ChatContextType => {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}

interface ChatProviderProps {
  children: ReactNode
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [isLoading, setIsLoading] = useState(false)
  const [isLLMThinking, setIsLLMThinking] = useState(false)  // Global LLM thinking status
  const { memoryEnabled } = useMemory()
  const currentProfile = 'pfc'
  
  // 从SessionContext获取会话相关状态和方法
  const {
    currentSessionId,
    refreshSessions: sessionRefreshSessions,
    switchSession: sessionSwitchSession
  } = useSession()
  
  // 使用重构的消息管理钩子
  const {
    messages,
    setMessages,
    deleteMessage,
    clearChat,
    sendMessage: createAndSendMessage,
    addVideoMessage,
    updateMessageStatus
  } = useChatMessage({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    currentProfile,
    memoryEnabled,
    setIsLLMThinking  // Pass LLM thinking status setter
  })

  // Use streaming update handler for real-time thinking/text content
  useStreamingUpdateHandler({ setMessages, setIsLLMThinking })

  // Use stream processing hook for SSE metadata events only
  const { processStreamResponse: handleStreamResponse } = useStreamHandler({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    setMessages
  })

  // Main message sending function - now coordinates message sending and both SSE/WebSocket processing
  const sendMessage = useCallback(async (text: string, files: FileData[] = [], mentionedFiles: string[] = []) => {
    if (text.trim() === '' && files.length === 0) return

    try {
      // Use basic message creation and sending functionality from useChatMessage
      const { userMessageId, botMessageId, response } = await createAndSendMessage(text, files, mentionedFiles)

      // Handle streaming response (SSE metadata events)
      await handleStreamResponse(response, { userMessageId, botMessageId })

    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      setIsLoading(false)
    }
  }, [createAndSendMessage, handleStreamResponse])


  return (
    <ChatContext.Provider value={{
      messages,
      isLoading,
      isLLMThinking,
      sendMessage,
      clearChat,
      deleteMessage,
      addVideoMessage
    }}>
      {children}
    </ChatContext.Provider>
  )
}
