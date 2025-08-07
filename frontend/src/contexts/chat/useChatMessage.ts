/**
 * useChatMessage Hook
 * 
 * 负责聊天消息的 CRUD 操作和会话历史加载
 * - 消息状态管理 (messages, setMessages)
 * - 会话历史加载和转换
 * - 删除消息
 * - 清空聊天
 */

import { useState, useCallback, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, MessageStatus } from '../../types/chat'
import { sessionService, chatService } from '../../services/api'

export interface UseChatMessageOptions {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
}

export interface UseChatMessageReturn {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  deleteMessage: (messageId: string) => Promise<void>
  clearChat: () => void
}

export const useChatMessage = ({
  currentSessionId,
  sessionRefreshSessions,
  sessionSwitchSession
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
                if (msg.role === 'user' && !msg.tool_request) return true
                if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) return true
                if (msg.role === 'image') return true
                return false
              })
              .map((msg: any): Message | null => {
                let sender: 'user' | 'bot'
                if (msg.role === 'user' && !msg.tool_request) {
                  sender = 'user'
                } else if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) {
                  sender = 'bot'
                } else if (msg.role === 'image') {
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
                } else if (typeof msg.content === 'string') {
                  text = msg.content
                } else if (Array.isArray(msg.content)) {
                  const textContents = msg.content
                    .filter((item: any) => item.text)
                    .map((item: any) => item.text)
                  text = textContents.join('\n')
                  
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
                    toolName: msg.tool_state.tool_name,
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

  return {
    messages,
    setMessages,
    deleteMessage,
    clearChat
  }
}