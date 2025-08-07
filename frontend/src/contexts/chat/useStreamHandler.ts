import { useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, MessageStatus } from '../../types/chat'
import { playMotion } from '../../utils/live2d'

interface UseStreamHandlerProps {
  ttsEnabled: boolean
  currentSessionId: string | null
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  updateMessageStatus: (messageId: string, status: MessageStatus) => void
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setToolState: (state: any) => void
}

interface StreamHandlerOptions {
  userMessageId: string
  botMessageId: string
}

export const useStreamHandler = ({
  ttsEnabled,
  currentSessionId,
  processAudioData,
  sessionRefreshSessions,
  sessionSwitchSession,
  updateMessageStatus,
  setMessages,
  setToolState
}: UseStreamHandlerProps) => {

  const processStreamResponse = useCallback(async (
    response: Response, 
    options: StreamHandlerOptions
  ) => {
    const { userMessageId, botMessageId } = options

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法读取响应流')
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let currentKeyword: string | null = null
    let audioCount = 0
    let firstResponseReceived = false
    let finalAiMessageId: string | null = null
    
    let isProcessingChunk = false
    let chunkQueue: {text: string, audio?: string, index?: number, next?: any}[] = []
    let chunkBuffer: Map<number, {text: string, audio?: string, next?: any}> = new Map()
    let expectedChunkIndex = 0

    // 处理标题更新事件
    const handleTitleUpdate = (data: any) => {
      if (data.payload && data.payload.session_id && data.payload.title) {
        sessionRefreshSessions().catch(error => {
          console.error('刷新会话列表失败:', error)
        })
      }
    }

    // 处理会话刷新事件
    const handleSessionRefresh = async (data: any) => {
      if (data.payload && data.payload.session_id) {
        const { session_id: refreshSessionId } = data.payload
        
        if (refreshSessionId === currentSessionId) {
          try {
            const response = await fetch(`/api/history/${refreshSessionId}`)
            if (!response.ok) {
              throw new Error(`获取会话历史失败: ${response.status}`)
            }
            
            const historyData = await response.json()
            if (!historyData.history || !Array.isArray(historyData.history)) {
              throw new Error('无效的历史数据格式')
            }

            const lastImageMessage = historyData.history
              .filter((msg: any) => msg.role === 'image')
              .pop()

            if (lastImageMessage) {
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
              }

              setMessages(prev => [...prev, imageMessage])
            }
          } catch (error) {
            console.error('刷新会话内容失败:', error)
            await sessionSwitchSession(refreshSessionId)
          }
        }
      }
    }

    // 处理消息状态更新
    const handleStatusUpdate = (data: any) => {
      if (data.status === 'sent') {
        updateMessageStatus(userMessageId, MessageStatus.SENT)
      } else if (data.status === 'read') {
        updateMessageStatus(userMessageId, MessageStatus.READ)
      } else if (data.status === 'error') {
        console.error('消息处理错误:', data.error)
        updateMessageStatus(userMessageId, MessageStatus.ERROR)
      }
    }

    // 处理AI消息ID
    const handleAiMessageId = (data: any) => {
      if (data.message_id && !finalAiMessageId) {
        const newAiMessageId = data.message_id
        finalAiMessageId = newAiMessageId
        
        console.log(`[handleAiMessageId] 更新消息ID: ${botMessageId} -> ${finalAiMessageId}`)
        
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId) {
              console.log(`[handleAiMessageId] 找到并更新消息: ${botMessageId} -> ${finalAiMessageId}`)
              return { ...msg, id: finalAiMessageId! }
            }
            return msg
          })
        )
      }
    }

    // 处理关键词和动作
    const handleKeyword = (data: any) => {
      if (data.keyword && data.keyword !== currentKeyword) {
        currentKeyword = data.keyword
        
        if (currentKeyword) {
          playMotion(currentKeyword)
        }
      }
    }

    // 处理工具状态
    const handleToolState = (data: any) => {
      if (data.type === 'NAGISA_IS_USING_TOOL') {
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return {
                ...msg,
                toolState: {
                  isUsingTool: true,
                  toolName: data.tool_name,
                  action: data.action_text
                }
              }
            }
            return msg
          })
        )
        setToolState(data)
      } else if (data.type === 'NAGISA_TOOL_USE_CONCLUDED') {
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return {
                ...msg,
                toolState: {
                  isUsingTool: false
                }
              }
            }
            return msg
          })
        )
        setToolState(data)
      }
    }

    // 处理第一次响应
    const handleFirstResponse = (data: any) => {
      if (!firstResponseReceived && data.keyword) {
        firstResponseReceived = true
      }
    }

    // 处理文本和音频内容
    const handleContentUpdate = (data: any) => {
      if (!data) return
      
      console.log(`收到新的文本和音频chunk:`, data)
      
      if (data.index !== undefined && typeof data.index === 'number') {
        handleOrderedChunk(data)
      } else {
        handleUnorderedChunk(data)
      }
    }

    // 处理有序chunk（带index字段）
    const handleOrderedChunk = (data: any) => {
      const chunkIndex = data.index
      
      chunkBuffer.set(chunkIndex, {
        text: data.text || '',
        audio: data.audio,
        next: data.next
      })
      
      console.log(`缓存chunk #${chunkIndex}，期望index: ${expectedChunkIndex}`)
      
      while (chunkBuffer.has(expectedChunkIndex)) {
        const chunk = chunkBuffer.get(expectedChunkIndex)!
        chunkBuffer.delete(expectedChunkIndex)
        
        console.log(`处理有序chunk #${expectedChunkIndex}`)
        
        chunkQueue.push({
          text: chunk.text,
          audio: chunk.audio,
          index: expectedChunkIndex,
          next: chunk.next
        })
        
        expectedChunkIndex++
        
        if (!isProcessingChunk) {
          console.log('开始处理有序chunk队列')
          isProcessingChunk = true
          processNextChunk(chunkQueue.shift()).catch(err => {
            console.error('处理有序chunk队列时出错:', err)
            isProcessingChunk = false
          })
        }
      }
    }

    // 处理无序chunk（兼容旧格式）
    const handleUnorderedChunk = (data: any) => {
      chunkQueue.push({
        text: data.text || '',
        audio: data.audio,
        next: data.next
      })
      
      if (!isProcessingChunk) {
        console.log('开始处理无序chunk队列')
        isProcessingChunk = true
        processNextChunk(chunkQueue.shift()).catch(err => {
          console.error('处理无序chunk队列时出错:', err)
          isProcessingChunk = false
        })
      } else {
        console.log('当前有chunk正在处理，新chunk已加入队列，等待处理')
      }
    }

    // 处理一个chunk的文本和音频
    const processNextChunk = async (chunk: any) => {
      if (!chunk) {
        isProcessingChunk = false
        return
      }

      try {
        if (chunk.text !== undefined && chunk.text !== null) {
          let newText = ''
          if (typeof chunk.text === 'string') {
            newText = chunk.text
          } else if (Array.isArray(chunk.text)) {
            newText = chunk.text.filter((t: unknown) => typeof t === 'string').join('')
          }

          if (newText.length > 0) {
            const renderPromise = new Promise<void>((resolve) => {
              setMessages(prev => {
                const currentMsg = prev.find(msg => msg.id === (finalAiMessageId || botMessageId))
                const existingText = currentMsg?.text && typeof currentMsg.text === 'string' ? currentMsg.text : ''
                const updatedText = existingText + newText
                
                return prev.map(msg => {
                  if (msg.id === (finalAiMessageId || botMessageId)) {
                    return {
                      ...msg,
                      text: updatedText,
                      newText,
                      streaming: true,
                      isLoading: updatedText.length < 10,
                      onRenderComplete: resolve
                    }
                  }
                  return msg
                })
              })
            })

            await renderPromise
            await new Promise(resolve => setTimeout(resolve, 10))
          }
        }

        if (ttsEnabled && chunk.audio && typeof chunk.audio === 'string' && chunk.audio.length > 0) {
          try {
            console.log('开始处理音频...')
            await processAudioData(chunk.audio, audioCount++)
            console.log('音频处理完成')
          } catch (error) {
            console.error('音频处理失败:', error)
          }
        }

        if (chunk.next) {
          await processNextChunk(chunk.next)
        } else {
          const nextChunk = chunkQueue.shift()
          if (nextChunk) {
            await processNextChunk(nextChunk)
          } else {
            setMessages(prev => 
              prev.map(msg => {
                if (msg.id === (finalAiMessageId || botMessageId)) {
                  const finalText = msg.text && typeof msg.text === 'string' ? msg.text : ''
                  return {
                    ...msg,
                    text: finalText,
                    streaming: false,
                    isLoading: false,
                    id: finalAiMessageId || botMessageId,
                    newText: undefined,
                    onRenderComplete: undefined
                  }
                }
                return msg
              })
            )
            isProcessingChunk = false
          }
        }
      } catch (error) {
        console.error('处理chunk时出错:', error)
        isProcessingChunk = false
      }
    }

    // 处理一行数据
    const processLine = (line: string) => {
      if (line.trim() === '') return
      
      if (line.startsWith('data: ')) {
        const jsonData = line.slice(6)
        
        try {
          const data = JSON.parse(jsonData)
          
          if (data.type === 'TITLE_UPDATE') {
            handleTitleUpdate(data)
            return
          }
          
          if (data.type === 'SESSION_REFRESH') {
            handleSessionRefresh(data)
            return
          }
          
          if (data.status) {
            handleStatusUpdate(data)
            return
          }
          
          handleAiMessageId(data)
          handleFirstResponse(data)
          handleKeyword(data)
          
          if (data.type === 'NAGISA_IS_USING_TOOL' || data.type === 'NAGISA_TOOL_USE_CONCLUDED') {
            handleToolState(data)
            return
          }
          
          handleContentUpdate(data)
        } catch (e) {
          console.error('解析响应数据时出错:', e)
        }
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        while (chunkQueue.length > 0 || isProcessingChunk) {
          await new Promise(resolve => setTimeout(resolve, 100))
        }
        
        chunkQueue = []
        chunkBuffer.clear()
        expectedChunkIndex = 0
        isProcessingChunk = false
        buffer = ''
        console.log('[DEBUG] Stream processing completed, all state cleared including ordering buffer')
        
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return { 
                ...msg, 
                streaming: false,
                id: finalAiMessageId || botMessageId
              }
            }
            return msg
          })
        )
        
        sessionRefreshSessions()
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        processLine(line)
      }
    }
  }, [
    ttsEnabled,
    currentSessionId,
    processAudioData,
    sessionRefreshSessions,
    sessionSwitchSession,
    updateMessageStatus,
    setMessages,
    setToolState
  ])

  return {
    processStreamResponse
  }
}