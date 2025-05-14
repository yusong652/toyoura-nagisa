import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType } from '../types/chat'
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
  const { queueAndPlayAudio, resetAudioState } = useAudio()

  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return

    // 添加用户消息
    const userMessage: Message = {
      id: uuidv4(),
      sender: 'user',
      text,
      files,
      timestamp: Date.now()
    }
    
    setMessages(prev => [...prev, userMessage])
    
    // 重置音频状态
    console.log('重置音频状态')
    await resetAudioState()
    
    // 设置加载状态
    setIsLoading(true)
    
    try {
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
          session_id: localStorage.getItem('session_id') || undefined,
        }),
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      // 创建机器人回复消息
      const botMessage: Message = {
        id: uuidv4(),
        sender: 'bot',
        text: '',
        timestamp: Date.now()
      }
      
      setMessages(prev => [...prev, botMessage])
      
      // 处理流式响应
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentText = ''
      let currentKeyword = null
      let audioCount = 0
      let pendingAudioQueue: string[] = [] // 用于存储接收到的音频数据
      
      console.log('开始处理流式响应')
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          console.log('流式响应结束')
          
          // 确保所有接收到的音频数据都被处理
          if (pendingAudioQueue.length > 0) {
            console.log(`响应结束时还有 ${pendingAudioQueue.length} 段音频未处理，开始处理...`)
            for (const audioData of pendingAudioQueue) {
              await new Promise(resolve => {
                queueAndPlayAudio(audioData)
                // 等待一小段时间确保音频被添加到队列
                setTimeout(resolve, 100)
              })
            }
          }
          
          break
        }
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.text) {
                // 更新文本显示
                currentText += data.text
                setMessages(prev => 
                  prev.map(msg => 
                    msg.id === botMessage.id 
                      ? { ...msg, text: currentText } 
                      : msg
                  )
                )
              }
              
              if (data.keyword && !currentKeyword) {
                // 只在第一次收到关键词时触发动作
                currentKeyword = data.keyword
                console.log('收到关键词，触发动作:', currentKeyword)
                // 这里可以调用Live2D动作
                playMotion(currentKeyword)
              }
              
              if (data.audio) {
                audioCount++
                console.log(`收到第 ${audioCount} 段音频数据，长度: ${data.audio.length}`)
                
                // 验证音频数据是否有效
                if (typeof data.audio === 'string' && data.audio.length > 0) {
                  try {
                    // 尝试解码一小部分以验证格式是否正确
                    const testBuffer = Uint8Array.from(atob(data.audio.slice(0, 100)), c => c.charCodeAt(0)).buffer
                    console.log('音频数据有效，添加到播放队列')
                    
                    // 将音频添加到队列并播放
                    queueAndPlayAudio(data.audio)
                    
                    // 给音频处理一些时间
                    await new Promise(resolve => setTimeout(resolve, 50))
                  } catch (error) {
                    console.error('音频数据格式无效:', error)
                  }
                } else {
                  console.warn('收到空的音频数据或格式不正确')
                }
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('Error sending message:', error)
      // 添加错误消息
      setMessages(prev => [
        ...prev, 
        {
          id: uuidv4(),
          sender: 'bot',
          text: `Error: ${(error as Error).message}`,
          timestamp: Date.now()
        }
      ])
    } finally {
      setIsLoading(false)
    }
  }, [queueAndPlayAudio, resetAudioState])

  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  return (
    <ChatContext.Provider value={{ messages, isLoading, sendMessage, clearChat }}>
      {children}
    </ChatContext.Provider>
  )
} 