import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { FileData, ChatContextType} from '../../types/chat'
import { useAudio } from '../audio/AudioContext'
import { useTtsEnable } from '../audio/TtsEnableContext'
import { useAgent } from '../agent/AgentContext'
import { useSession } from '../session/SessionContext'
import { useMemory } from '../MemoryContext'
import { useChatMessage } from './useChatMessage'
import { useStreamHandler } from './useStreamHandler'
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
    toolState,
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
      console.log(`Starting audio playback #${count}, waiting for completion...`);
      // Wait for audio playback to complete before returning
      const startTime = Date.now();
      await queueAndPlayAudio(audioData);
      const duration = (Date.now() - startTime) / 1000;
      console.log(`Audio #${count} playback completed, duration: ${duration.toFixed(2)}s`);
      return true;
    } catch (error) {
      console.error(`Audio #${count} processing failed:`, error);
      return false;
    }
  }, [queueAndPlayAudio])


  // Use stream processing hook
  const { processStreamResponse: handleStreamResponse } = useStreamHandler({
    ttsEnabled,
    currentSessionId,
    processAudioData,
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

  // Main message sending function - now only coordinates message sending and stream processing
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return
    
    // Reset audio state - ensure cleanup of residual state from previous requests
    await resetAudioState()
    
    try {
      // Use basic message creation and sending functionality from useChatMessage
      const { userMessageId, botMessageId, response } = await createAndSendMessage(text, files)

      // Handle streaming response (including audio, Live2D, tool status, etc.)
      await handleStreamResponse(response, { userMessageId, botMessageId })
    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      setIsLoading(false)
    }
  }, [createAndSendMessage, handleStreamResponse, resetAudioState])


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
