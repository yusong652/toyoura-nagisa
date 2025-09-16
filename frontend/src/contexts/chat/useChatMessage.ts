/**
 * useChatMessage Hook
 * 
 * 负责聊天消息的完整管理
 * - 消息状态管理 (messages, setMessages)
 * - 发送消息 (包括创建用户消息和机器人消息)
 * - 会话历史加载和转换
 * - 删除消息
 * - 清空聊天
 * - 消息状态更新
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

  // 当会话变化时，重新加载消息
  useEffect(() => {
    if (currentSessionId) {
      // 直接调用内部消息加载逻辑，而不是通过 switchSession 包装器
      const loadMessages = async () => {
        try {
          const historyData = await sessionService.getSessionHistory(currentSessionId)
          if (historyData.history && Array.isArray(historyData.history)) {
            const convertedMessages: Message[] = historyData.history
              .filter((msg: any) => {
                return (msg.role === 'user' && !msg.tool_request) ||
                       (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) ||
                       (msg.role === 'image') ||
                       (msg.role === 'video')
              })
              .map((msg: any): Message | null => {
                let sender: 'user' | 'bot'
                if (msg.role === 'user' && !msg.tool_request) {
                  sender = 'user'
                } else if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) {
                  sender = 'bot'
                } else if (msg.role === 'image') {
                  sender = 'bot'
                } else if (msg.role === 'video') {
                  sender = 'bot'
                } else {
                  return null
                }

                let text = ''
                let files: any[] = []

                if (msg.role === 'image') {
                  text = msg.content || ''
                  files.push({
                    name: 'generated_image',
                    type: 'image/png',
                    data: `/api/images/${msg.image_path}`
                  })
                } else if (msg.role === 'video') {
                  text = msg.content || ''
                  // 根据文件扩展名确定视频类型
                  const videoPath = msg.video_path
                  // 从路径中提取文件名 (格式: session_id/filename.ext)
                  const filename = videoPath?.split('/').pop() || 'video.mp4'
                  const extension = filename.toLowerCase().split('.').pop()
                  let mediaType = 'video/mp4' // 默认
                  
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
                  // 如果assistant消息为空（可能只有表情），添加占位符
                  if (msg.role === 'assistant' && !text) {
                    text = '...'  // 使用省略号作为占位符，表示只有表情动作
                  }
                } else if (Array.isArray(msg.content)) {
                  // 处理content数组，兼容直接text和type字段
                  const textContents = msg.content
                    .filter((item: any) => {
                      // 兼容两种格式：直接有text字段，或者type为text
                      return item.text || (item.type === 'text' && item.text)
                    })
                    .map((item: any) => item.text)
                  
                  let rawText = textContents.join('\n')
                  
                  // 解析并处理[[keyword]]标记
                  if (msg.role === 'assistant') {
                    const keywordMatch = rawText.match(/\[\[(\w+)\]\]/);
                    if (keywordMatch) {
                      // 移除keyword标记
                      const textWithoutKeyword = rawText.replace(/\[\[\w+\]\]/g, '').trim();
                      
                      if (!textWithoutKeyword) {
                        // 只有keyword，显示占位符
                        text = '...';
                      } else {
                        // 有keyword和文本，只显示文本
                        text = textWithoutKeyword;
                      }
                    } else {
                      // 没有keyword标记
                      text = rawText;
                      
                      // 兜底：如果assistant消息为空，添加占位符
                      if (!text.trim()) {
                        text = '...';
                      }
                    }
                  } else {
                    // 非assistant消息，直接使用原文本
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
                  sender,
                  text,
                  files: files.length > 0 ? files : undefined,
                  timestamp: new Date(msg.timestamp || Date.now()).getTime(),
                  status: sender === 'user' ? MessageStatus.READ : undefined,
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
          console.error('加载会话消息失败:', error)
          setMessages([])
        }
      }
      loadMessages()
    } else {
      setMessages([])
    }
  }, [currentSessionId])

  // 删除消息
  const deleteMessage = useCallback(async (messageId: string): Promise<void> => {
    // 确保有当前会话ID
    if (!currentSessionId) {
      throw new Error("没有活动的会话");
    }
    
    try {
      // 先检查消息是否存在于当前消息列表中
      const messageExists = messages.some(msg => msg.id === messageId);
      if (!messageExists) {
        console.error(`消息 ${messageId} 不存在于当前会话中`);
        throw new Error("消息不存在于当前会话中");
      }
      
      // 首先在前端更新消息列表，删除指定消息
      setMessages(prev => prev.filter(msg => msg.id !== messageId));
      
      // 调用后端API删除消息
      const responseData = await chatService.deleteMessage(currentSessionId, messageId);
      
      if (!responseData.success) {
        console.error('删除消息失败:', responseData);
        
        // 如果后端删除失败但前端已移除，恢复被删除的消息
        await sessionSwitchSession(currentSessionId);
        throw new Error(`删除消息失败: ${responseData.detail}`);
      }
      
      // 删除成功后刷新会话列表
      await sessionRefreshSessions();
    } catch (error) {
      console.error('删除消息失败:', error);
      throw error;
    }
  }, [currentSessionId, sessionRefreshSessions, messages, sessionSwitchSession]);

  // 清空聊天
  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  // 添加用户消息
  const addUserMessage = useCallback((text: string, files: FileData[] = []): string => {
    const userMessage: Message = {
      id: uuidv4(),
      sender: 'user',
      text,
      files: files.length > 0 ? files : undefined,
      timestamp: Date.now(),
      status: MessageStatus.SENDING
    }
    
    setMessages(prev => [...prev, userMessage])
    return userMessage.id
  }, [])


  // 添加视频消息
  const addVideoMessage = useCallback((videoPath: string, content: string = "") => {
    const videoMessageId = uuidv4()
    // 从路径中提取文件名 (格式: session_id/filename.ext)
    const filename = videoPath.split('/').pop() || 'video.mp4'
    const extension = filename.toLowerCase().split('.').pop()
    let mediaType = 'video/mp4' // 默认
    
    if (extension === 'gif') {
      mediaType = 'image/gif'
    } else if (extension === 'webm') {
      mediaType = 'video/webm'
    } else if (extension === 'mp4') {
      mediaType = 'video/mp4'
    }
    
    const videoMessage: Message = {
      id: videoMessageId,
      sender: 'bot',
      text: content, // 空内容，只显示视频
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

  // 更新消息状态
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
      const { messageId, sender, initialText, streaming } = customEvent.detail

      if (sender === 'bot') {
        // Create new bot message with specified ID
        const newBotMessage: Message = {
          id: messageId,
          sender: 'bot',
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

  // 更新机器人消息
  const updateBotMessage = useCallback((messageId: string, updates: Partial<Message>) => {
    setMessages(prev => {
      const updatedMessages = prev.map(msg => {
        if (msg.id === messageId) {
          const updatedMsg = { ...msg, ...updates }
          // 如果更新包含新的ID，确保保持消息的完整性
          if (updates.id && updates.id !== messageId) {
            console.log(`[updateBotMessage] 更新消息ID: ${messageId} -> ${updates.id}`)
          }
          return updatedMsg
        }
        return msg
      })
      
      // 验证消息是否存在
      const messageFound = updatedMessages.some(msg => 
        msg.id === messageId || (updates.id && msg.id === updates.id)
      )
      if (!messageFound) {
        console.warn(`[updateBotMessage] 警告: 未找到ID为 ${messageId} 的消息`)
      }
      
      return updatedMessages
    })
  }, [])


  // 创建并发送消息的基础函数
  // 职责：创建用户消息 -> 调用后端API -> 创建机器人消息占位符
  // 不包含：音频处理、流式响应处理、Live2D动作等高级功能
  const sendMessage = useCallback(async (
    text: string, 
    files: FileData[] = []
  ): Promise<{
    userMessageId: string
    botMessageId: string
    response: Response
  }> => {
    if (text.trim() === '' && files.length === 0) {
      throw new Error('消息内容不能为空')
    }
    
    // 创建用户消息
    const userMessageId = addUserMessage(text, files)
    
    try {
      // 创建API请求
      const sessionId = currentSessionId || localStorage.getItem('session_id') || "default_session"
      const response = await chatService.sendMessage(text, files, sessionId, userMessageId, currentProfile, ttsEnabled, memoryEnabled)

      return {
        userMessageId,
        botMessageId: '', // 不再需要占位符ID
        response
      }
    } catch (error) {
      // 更新消息为错误状态
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