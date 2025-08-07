import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, MessageStatus } from '../../types/chat'
import { useAudio } from '../audio/AudioContext'
import { useTools } from '../tools/ToolsContext'
import { useSession } from '../session/SessionContext'
import { playMotion } from '../../utils/live2d'
import { chatService, sessionService } from '../../services/api'
import { useChatMessage } from './useChatMessage'
import { useStreamHandler } from './useStreamHandler'

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
  const {
    toolState,
    toolsEnabled,
    ttsEnabled,
    updateToolsEnabled,
    updateTtsEnabled,
    setToolState
  } = useTools()
  
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
    updateMessageStatus,
    updateBotMessage
  } = useChatMessage({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    ttsEnabled
  })

  // 处理音频数据 - 确保返回一个Promise，该Promise在音频播放完成后resolve
  const processAudioData = useCallback(async (audioData: string, count: number): Promise<boolean> => {
    if (typeof audioData !== 'string' || audioData.length === 0) {
      console.warn('收到空的音频数据或格式不正确')
      return false
    }
    
    try {
      console.log(`开始播放音频 #${count}，等待播放完成...`);
      // 等待音频播放完成后再返回
      const startTime = Date.now();
      await queueAndPlayAudio(audioData);
      const duration = (Date.now() - startTime) / 1000;
      console.log(`音频 #${count} 已完成播放，耗时: ${duration.toFixed(2)}秒`);
      return true;
    } catch (error) {
      console.error(`音频 #${count} 处理失败:`, error);
      return false;
    }
  }, [queueAndPlayAudio])

  // 使用流式处理钩子
  const { processStreamResponse: handleStreamResponse } = useStreamHandler({
    ttsEnabled,
    currentSessionId,
    processAudioData,
    sessionRefreshSessions,
    sessionSwitchSession,
    updateMessageStatus,
    setMessages,
    setToolState
  })


  // 注意：会话相关的功能已经移至 SessionContext，组件应直接使用 useSession()
  // 消息管理功能已经移至 useChatMessage 钩子



  // 主发送消息函数 - 现在只负责协调消息发送和流处理
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return
    
    // 重置音频状态 - 确保清理上一次请求的残留状态
    await resetAudioState()
    console.log('[DEBUG] Starting new message request, audio state reset');
    
    try {
      // 使用useChatMessage提供的基础消息创建和发送功能
      const { userMessageId, botMessageId, response } = await createAndSendMessage(text, files)
      
      // 处理流式响应（包括音频、Live2D、工具状态等）
      await handleStreamResponse(response, { userMessageId, botMessageId })
    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      setIsLoading(false)
    }
  }, [createAndSendMessage, handleStreamResponse, resetAudioState])

  // 一键生成图片
  const generateImage = useCallback(async (sessionId: string): Promise<{success: boolean, image_path?: string, error?: string}> => {
    const result = await chatService.generateImage(sessionId);
    
    // 如果图片生成成功，重新获取会话历史以获取最新的图片消息
    if (result.success && sessionId === currentSessionId) {
      try {
        // 获取最新的会话历史
        const historyData = await sessionService.getSessionHistory(sessionId);
        if (historyData.history && Array.isArray(historyData.history)) {
          // 找到最后一条图片消息
          const lastImageMessage = historyData.history
            .filter((msg: any) => msg.role === 'image')
            .pop();

          if (lastImageMessage) {
            // 创建图片消息对象
            const imageMessage: Message = {
              id: lastImageMessage.id || uuidv4(),
              sender: 'bot',
              text: lastImageMessage.content || '',
              timestamp: new Date(lastImageMessage.timestamp || Date.now()).getTime(),
              files: [{
                name: 'generated_image',
                type: 'image/png',
                data: `/api/images/${lastImageMessage.image_path}`
              }]
            };

            // 添加图片消息到当前消息列表
            setMessages(prev => [...prev, imageMessage]);
          }
        }
      } catch (error) {
        console.error('获取生成的图片消息失败:', error);
      }
    }
    
    return result;
  }, [currentSessionId]);

  return (
    <ChatContext.Provider value={{
      messages,
      isLoading,
      sendMessage,
      clearChat,
      deleteMessage,
      toolState,
      toolsEnabled,
      updateToolsEnabled,
      generateImage,
      ttsEnabled,
      updateTtsEnabled
    }}>
      {children}
    </ChatContext.Provider>
  )
}
