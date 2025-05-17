import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, ChatSession } from '../types/chat'
import { useAudio } from './AudioContext.tsx'
import { playMotion } from '../utils/live2d'

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
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [loadingMessageId, setLoadingMessageId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const { queueAndPlayAudio, resetAudioState } = useAudio()

  // 初始化：创建新会话或加载已有会话
  useEffect(() => {
    const init = async () => {
      // 检查本地存储是否有会话ID
      const storedSessionId = localStorage.getItem('session_id')
      
      if (storedSessionId) {
        // 如果有存储的会话ID，尝试切换到该会话
        try {
          await switchSession(storedSessionId)
        } catch (error) {
          console.error('无法加载已存储的会话，创建新会话', error)
          await createNewSession()
        }
      } else {
        // 如果没有存储的会话ID，创建新会话
        await createNewSession()
      }
      
      // 刷新会话列表
      await refreshSessions()
    }
    
    init()
  }, [])

  // 创建新会话
  const createNewSession = useCallback(async (name?: string): Promise<string> => {
    try {
      const response = await fetch('/api/history/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      const newSessionId = data.session_id
      
      // 保存到本地存储
      localStorage.setItem('session_id', newSessionId)
      
      // 更新当前会话ID
      setCurrentSessionId(newSessionId)
      
      // 清空消息
      setMessages([])
      
      // 刷新会话列表
      await refreshSessions()
      
      return newSessionId
    } catch (error) {
      console.error('创建新会话失败:', error)
      throw error
    }
  }, [])

  // 切换会话
  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
    try {
      const response = await fetch('/api/history/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      
      // 保存到本地存储
      localStorage.setItem('session_id', sessionId)
      
      // 更新当前会话ID
      setCurrentSessionId(sessionId)
      
      // 获取完整会话历史
      const historyResponse = await fetch(`/api/history/${sessionId}`)
      if (!historyResponse.ok) {
        throw new Error(`获取历史记录失败: ${historyResponse.status}`)
      }
      
      const historyData = await historyResponse.json()
      
      // 将后端消息格式转换为前端格式
      const convertedMessages: Message[] = historyData.history.map((msg: any) => {
        // 判断是用户消息还是机器人消息
        const sender = msg.role === 'user' ? 'user' : 'bot'
        
        // 提取文本内容
        let text = ''
        let files: FileData[] = []
        
        if (typeof msg.content === 'string') {
          text = msg.content
        } else if (Array.isArray(msg.content)) {
          // 处理多模态内容
          msg.content.forEach((item: any) => {
            if (item.text) {
              text = item.text
            } else if (item.inline_data) {
              files.push({
                name: `image_${files.length + 1}`,
                type: item.inline_data.mime_type,
                data: `data:${item.inline_data.mime_type};base64,${item.inline_data.data}`
              })
            }
          })
        }
        
        return {
          id: uuidv4(), // 生成新的ID
          sender,
          text,
          files: files.length > 0 ? files : undefined,
          timestamp: new Date(msg.timestamp).getTime(),
          isRead: true
        }
      })
      
      // 更新消息列表
      setMessages(convertedMessages)
      
    } catch (error) {
      console.error('切换会话失败:', error)
      throw error
    }
  }, [])

  // 删除会话
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    try {
      const response = await fetch(`/api/history/${sessionId}`, {
        method: 'DELETE',
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      // 如果删除的是当前会话，创建新会话
      if (sessionId === currentSessionId) {
        await createNewSession()
      }
      
      // 刷新会话列表
      await refreshSessions()
    } catch (error) {
      console.error('删除会话失败:', error)
      throw error
    }
  }, [currentSessionId, createNewSession])

  // 刷新会话列表
  const refreshSessions = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch('/api/history/sessions')
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setSessions(data)
    } catch (error) {
      console.error('获取会话列表失败:', error)
      throw error
    }
  }, [])

  // 添加用户消息到聊天记录
  const addUserMessage = useCallback((text: string, files: FileData[] = []): string => {
    // 创建用户消息
    const userMessage: Message = {
      id: uuidv4(),
      sender: 'user',
      text,
      files,
      timestamp: Date.now(),
      isRead: false // 初始状态为未读
    }
    
    // 添加到消息列表
    setMessages(prev => [...prev, userMessage])
    
    // 设置用户消息为已读状态（在发送消息1秒后）
    setTimeout(() => {
      setMessages(prev => 
        prev.map(msg => 
          msg.id === userMessage.id
            ? { ...msg, isRead: true }
            : msg
        )
      )
    }, 1000)
    
    return userMessage.id
  }, [])

  // 添加机器人加载消息
  const addLoadingMessage = useCallback((): string => {
    // 创建一个加载消息占位符
    const loadingId = uuidv4()
    setLoadingMessageId(loadingId)
    
    // 添加加载消息到聊天记录
    const loadingMessage: Message = {
      id: loadingId,
      sender: 'bot',
      text: '',
      timestamp: Date.now(),
      isLoading: true // 标记为加载中
    }
    
    setMessages(prev => [...prev, loadingMessage])
    setIsLoading(true)
    
    return loadingId
  }, [])

  // 更新加载消息为错误状态
  const updateMessageWithError = useCallback((loadingId: string, error: Error) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === loadingId 
          ? { ...msg, text: `Error: ${error.message}`, isLoading: false } 
          : msg
      )
    )
  }, [])

  // 处理音频数据
  const processAudioData = useCallback((audioData: string, count: number): boolean => {
    if (typeof audioData !== 'string' || audioData.length === 0) {
      console.warn('收到空的音频数据或格式不正确')
      return false
    }
    
    try {
      // 尝试解码一小部分以验证格式是否正确
      const testBuffer = Uint8Array.from(atob(audioData.slice(0, 100)), c => c.charCodeAt(0)).buffer
      console.log(`收到第 ${count} 段音频数据，长度: ${audioData.length}`)
      console.log('音频数据有效，添加到播放队列')
      
      // 将音频添加到队列并播放
      queueAndPlayAudio(audioData)
      return true
    } catch (error) {
      console.error('音频数据格式无效:', error)
      return false
    }
  }, [queueAndPlayAudio])

  // 创建聊天API请求
  const createChatRequest = useCallback(async (text: string, files: FileData[] = []): Promise<Response> => {
    // 构造请求数据
    const messageData = JSON.stringify({
      text,
      files: files.map(file => ({
        name: file.name,
        type: file.type,
        data: file.data
      }))
    })
    
    // 调用API
    console.log('发送聊天请求')
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messageData,
        session_id: currentSessionId || localStorage.getItem('session_id') || "default_session",
      }),
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response
  }, [currentSessionId])

  // 处理聊天API响应
  const processStreamResponse = useCallback(async (
    response: Response, 
    loadingId: string
  ) => {
    // 处理流式响应
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentText = ''
    let currentKeyword = null
    let audioCount = 0
    let firstResponseReceived = false
    
    console.log('开始处理流式响应')
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        console.log('流式响应结束')
        
        // 响应结束后，更新消息为最终状态
        setMessages(prev => 
          prev.map(msg => 
            msg.id === loadingId 
              ? { ...msg, text: currentText, isLoading: false, streaming: false } 
              : msg
          )
        )
        
        // 刷新会话列表以更新最新状态
        refreshSessions()
        
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      
      // 处理每一行数据
      for (const line of lines) {
        if (line.trim() === '') continue
        
        if (line.startsWith('data: ')) {
          const jsonData = line.slice(6)
          
          try {
            const data = JSON.parse(jsonData)
            
            // 如果是第一次收到响应，标记为已收到
            if (!firstResponseReceived) {
              firstResponseReceived = true
              // 播放Live2D动作
              playMotion('tap_body')
            }
            
            // 处理关键词
            if (data.keyword && data.keyword !== currentKeyword) {
              currentKeyword = data.keyword
              console.log('检测到关键词:', currentKeyword)
              
              // 根据关键词播放对应的Live2D动作
              // 表情关键词只在回复开始时发送一次
              playMotion(currentKeyword)
            }
            
            // 处理文本和音频（新的组合格式）
            if (data.text) {
              // 后端现在发送配对的文本和音频数据，确保同步
              currentText += data.text // 累加文本
              
              // 更新消息
              setMessages(prev => 
                prev.map(msg => 
                  msg.id === loadingId 
                    ? { ...msg, text: currentText, isLoading: false, streaming: true } 
                    : msg
                )
              )
              
              // 如果同时收到了音频数据，处理音频
              if (data.audio) {
                audioCount++
                processAudioData(data.audio, audioCount)
              }
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e)
          }
        }
      }
    }
  }, [refreshSessions, playMotion, processAudioData])
  
  // 主发送消息函数
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return
    
    // 添加用户消息
    addUserMessage(text, files)
    
    // 重置音频状态
    console.log('重置音频状态')
    await resetAudioState()
    
    // 添加机器人加载消息
    const loadingId = addLoadingMessage()
    
    try {
      // 创建并发送API请求
      const response = await createChatRequest(text, files)
      
      // 处理流式响应
      await processStreamResponse(response, loadingId)
    } catch (error) {
      console.error('Error sending message:', error)
      // 更新加载消息为错误消息
      updateMessageWithError(loadingId, error as Error)
    } finally {
      setIsLoading(false)
      setLoadingMessageId(null)
    }
  }, [addUserMessage, resetAudioState, addLoadingMessage, createChatRequest, processStreamResponse, updateMessageWithError])

  const clearChat = useCallback(() => {
    setMessages([])
    setLoadingMessageId(null)
  }, [])

  return (
    <ChatContext.Provider value={{ 
      messages, 
      isLoading, 
      loadingMessageId, 
      sessions, 
      currentSessionId,
      sendMessage, 
      clearChat, 
      createNewSession, 
      switchSession, 
      deleteSession, 
      refreshSessions 
    }}>
      {children}
    </ChatContext.Provider>
  )
} 