import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { FileData, ChatContextType} from '../../types/chat'
import { useAudio } from '../audio/AudioContext'
import { useTtsEnable } from '../audio/TtsEnableContext'
import { useAgent } from '../agent/AgentContext'
import { useSession } from '../session/SessionContext'
import { useMemory } from '../MemoryContext'
import { useChatMessage } from './useChatMessage'
import { useStreamHandler } from './useStreamHandler'
import { useWebSocketTTS } from './useWebSocketTTS'
import { useStreamingUpdateHandler } from './useStreamingUpdateHandler'
import { useMessageStateManager } from './useMessageStateManager'
import { useImageGenerator } from './useImageGenerator'
import { useVideoGenerator } from './useVideoGenerator'

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
  const { queueAndPlayAudio, resetAudioState } = useAudio()
  const { ttsEnabled } = useTtsEnable()
  const { memoryEnabled } = useMemory()
  const {
    toolsEnabled,
    currentProfile
  } = useAgent()
  
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
    ttsEnabled,
    currentProfile,
    memoryEnabled
  })

  // Process audio data - ensure Promise resolves after audio playback completes
  const processAudioData = useCallback(async (audioData: string, count: number): Promise<boolean> => {
    if (typeof audioData !== 'string' || audioData.length === 0) {
      console.warn('Received empty audio data or incorrect format')
      return false
    }

    try {
      // Wait for audio playback to complete before returning
      await queueAndPlayAudio(audioData);
      return true;
    } catch (error) {
      console.error(`Audio #${count} processing failed:`, error);
      return false;
    }
  }, [queueAndPlayAudio])

  // Use message state manager for WebSocket TTS processing
  const { updateMessageText, finalizeMessage } = useMessageStateManager({ setMessages })

  // Use WebSocket TTS handler
  const { setupTTSHandler, cleanupTTSHandler } = useWebSocketTTS({
    ttsEnabled,
    processAudioData,
    updateMessageText,
    finalizeMessage
  })

  // Use streaming update handler for real-time thinking/text content
  useStreamingUpdateHandler({ setMessages })

  // Use stream processing hook for SSE metadata events only
  const { processStreamResponse: handleStreamResponse } = useStreamHandler({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    setMessages
  })

  // Use image generation hook
  const { generateImage } = useImageGenerator({
    currentSessionId,
    setMessages
  })

  // Use video generation hook
  const { generateVideo } = useVideoGenerator({
    currentSessionId,
    setMessages
  })

  // Main message sending function - now coordinates message sending and both SSE/WebSocket processing
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return

    // Reset audio state - ensure cleanup of residual state from previous requests
    await resetAudioState()

    // Setup WebSocket TTS handler to process incoming TTS chunks
    setupTTSHandler()

    try {
      // Use basic message creation and sending functionality from useChatMessage
      const { userMessageId, botMessageId, response } = await createAndSendMessage(text, files)

      // Handle streaming response (SSE metadata events)
      await handleStreamResponse(response, { userMessageId, botMessageId })

      // Note: TTS processing will happen asynchronously via WebSocket

    } catch (error) {
      console.error('Error sending message:', error)
      // Cleanup TTS handler on error
      cleanupTTSHandler()
    } finally {
      setIsLoading(false)
    }
  }, [createAndSendMessage, handleStreamResponse, resetAudioState, setupTTSHandler, cleanupTTSHandler])


  return (
    <ChatContext.Provider value={{
      messages,
      isLoading,
      sendMessage,
      clearChat,
      deleteMessage,
      generateImage,
      generateVideo,
      addVideoMessage
    }}>
      {children}
    </ChatContext.Provider>
  )
}
