import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, ChatSession, ConnectionStatus } from '../types/chat'
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
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.CONNECTING)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const { queueAndPlayAudio, resetAudioState } = useAudio()
  const [sessionLoadAttempted, setSessionLoadAttempted] = useState(false);

  // 检查与后端的连接
  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      setConnectionStatus(ConnectionStatus.CONNECTING)
      setConnectionError(null)
      
      const response = await fetch('/api/history/sessions', { 
        signal: AbortSignal.timeout(5000) // 5秒超时
      })
      
      if (response.ok) {
        setConnectionStatus(ConnectionStatus.CONNECTED)
        return true
      } else {
        setConnectionStatus(ConnectionStatus.ERROR)
        setConnectionError(`服务器返回错误: ${response.status}`)
        return false
      }
    } catch (error) {
      console.error('连接检查失败:', error)
      setConnectionStatus(ConnectionStatus.DISCONNECTED)
      setConnectionError(error instanceof Error ? error.message : '无法连接到服务器')
      return false
    }
  }, [])

  // 刷新会话列表
  const refreshSessions = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch('/api/history/sessions')
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`获取会话列表失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setSessions(data)
      setConnectionStatus(ConnectionStatus.CONNECTED); // Successfully fetched
    } catch (error) {
      console.error('获取会话列表失败:', error);
      if (!(error instanceof DOMException && error.name === 'AbortError')) { // Don't set error if it's an abort
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(error instanceof Error ? error.message : '获取会话列表失败');
      }
      throw error;
    }
  }, [])

  // 创建新会话
  const createNewSession = useCallback(async (name?: string): Promise<string> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
         // checkConnection sets connectionError state.
         throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      const response = await fetch('/api/history/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
      })
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`创建新会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      const newSessionId = data.session_id
      
      localStorage.setItem('session_id', newSessionId)
      setCurrentSessionId(newSessionId)
      setMessages([])
      await refreshSessions()
      setConnectionStatus(ConnectionStatus.CONNECTED);
      return newSessionId
    } catch (error) {
      console.error('创建新会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '创建新会话失败');
      throw error;
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError])

  // 切换会话
  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
     if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        // checkConnection sets connectionError state.
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      const response = await fetch('/api/history/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      })
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`切换会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      localStorage.setItem('session_id', sessionId)
      setCurrentSessionId(sessionId)
      
      const historyResponse = await fetch(`/api/history/${sessionId}`)
      if (!historyResponse.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`获取历史记录失败: ${historyResponse.status}`);
        throw new Error(`获取历史记录失败: ${historyResponse.status}`)
      }
      
      const historyData = await historyResponse.json()
      const convertedMessages: Message[] = historyData.history.map((msg: any) => {
        const sender = msg.role === 'user' ? 'user' : 'bot'
        let text = ''
        let files: FileData[] = []
        if (typeof msg.content === 'string') {
          text = msg.content
        } else if (Array.isArray(msg.content)) {
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
          id: uuidv4(),
          sender,
          text,
          files: files.length > 0 ? files : undefined,
          timestamp: new Date(msg.timestamp).getTime(),
          isRead: true
        }
      })
      setMessages(convertedMessages)
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('切换会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '切换会话失败');
      throw error;
    }
  }, [connectionStatus, checkConnection, connectionError])

  // 删除会话
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        // checkConnection sets connectionError state.
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      const response = await fetch(`/api/history/${sessionId}`, {
        method: 'DELETE',
      })
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`删除会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      if (sessionId === currentSessionId) {
        await createNewSession()
      }
      await refreshSessions()
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('删除会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '删除会话失败');
      throw error;
    }
  }, [currentSessionId, createNewSession, refreshSessions, connectionStatus, checkConnection, connectionError])

  // 初始化 Effect: ComponentDidMount
  useEffect(() => {
    const initLoad = async () => {
      // Attempt to establish connection and load initial data
      const connected = await checkConnection();
      if (!connected) {
        setSessionLoadAttempted(true); // Mark that an initial load attempt failed due to connection
        return;
      }

      // Connection successful, now try to load session list and then the active session
      try {
        await refreshSessions(); // Load all session details first

        const storedSessionId = localStorage.getItem('session_id');
        if (storedSessionId) {
          try {
            await switchSession(storedSessionId); // This loads messages for the session
            setSessionLoadAttempted(false); // Successfully loaded a session
          } catch (switchError) {
            console.error('初始化时无法切换到已存储会话，尝试创建新会话:', switchError);
            if (connectionStatus === ConnectionStatus.CONNECTED) {
              try {
                await createNewSession(); // This loads messages for new session & refreshes list
                setSessionLoadAttempted(false); // Successfully created a new session
              } catch (createError) {
                console.error('初始化时创建新会话失败（切换会话后）:', createError);
                setSessionLoadAttempted(true); // Failed to establish a session
              }
            } else {
              setSessionLoadAttempted(true); // Connection lost during switchSession attempt
            }
          }
        } else {
          // No stored session, create a new one
          try {
            await createNewSession();
            setSessionLoadAttempted(false); // Successfully created a new session
          } catch (createError) {
            console.error('初始化时创建新会话失败（无存储ID）:', createError);
            setSessionLoadAttempted(true); // Failed to establish a session
          }
        }
      } catch (refreshError) {
        // Error from refreshSessions()
        console.error('初始化时加载会话列表失败:', refreshError);
        setSessionLoadAttempted(true); // Mark that the load was attempted and failed
      }
    };

    initLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once on mount

  // 尝试在重新连接后加载会话
  useEffect(() => {
    const loadSessionOnReconnect = async () => {
      if (connectionStatus === ConnectionStatus.CONNECTED && sessionLoadAttempted && !currentSessionId) {
        console.log("检测到重新连接，尝试加载/刷新会话...");
        setSessionLoadAttempted(false); // We are attempting to load now

        try {
          await refreshSessions(); // Load all session details first

          const storedSessionId = localStorage.getItem('session_id');
          if (storedSessionId) {
            try {
              await switchSession(storedSessionId);
              // Successfully loaded session on reconnect
            } catch (switchError) {
              console.error('重新连接后无法切换到已存储会话，尝试创建新会话:', switchError);
              if (connectionStatus === ConnectionStatus.CONNECTED) {
                try {
                  await createNewSession();
                } catch (createError) {
                  console.error('重新连接后创建新会话也失败（切换会话后）:', createError);
                  setSessionLoadAttempted(true); // Mark failed attempt
                }
              } else {
                 setSessionLoadAttempted(true); // Connection lost during switch
              }
            }
          } else {
            // No stored session, create a new one
            try {
              await createNewSession();
            } catch (createError) {
              console.error('重新连接后创建新会话失败（无存储ID）:', createError);
              setSessionLoadAttempted(true); // Mark failed attempt
            }
          }
        } catch (refreshError) {
          // Error from refreshSessions() during reconnect
          console.error('重新连接后加载会话列表失败:', refreshError);
          setSessionLoadAttempted(true); // Mark failed attempt so it can retry if connection cycles
        }
      }
    };

    loadSessionOnReconnect();
  }, [connectionStatus, sessionLoadAttempted, currentSessionId, refreshSessions, switchSession, createNewSession]);

  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return

    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        setMessages(prev => {
          const lastMessage = prev[prev.length -1];
          if (lastMessage && lastMessage.isLoading) {
            return prev.map(msg => msg.id === lastMessage.id ? { ...msg, text: `错误: 无法连接到服务器。请检查网络连接或稍后重试。`, isLoading: false } : msg)
          }
          return prev;
        });
        return;
      }
    }

    // 添加用户消息
    const userMessage: Message = {
      id: uuidv4(),
      sender: 'user',
      text,
      files,
      timestamp: Date.now(),
      isRead: false // 初始状态为未读
    }
    
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
    
    // 重置音频状态
    console.log('重置音频状态')
    await resetAudioState()
    
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
          session_id: currentSessionId || localStorage.getItem('session_id') || "default_session",
        }),
      })
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`发送消息失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      // 处理流式响应
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentText = ''
      let currentKeyword = null
      let audioCount = 0
      let pendingAudioQueue: string[] = [] // 用于存储接收到的音频数据
      let firstResponseReceived = false
      
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
              
              // 处理文本内容
              if (data.text) {
                currentText += data.text // 累加文本而不是替换
                
                // 更新消息
                setMessages(prev => 
                  prev.map(msg => 
                    msg.id === loadingId 
                      ? { ...msg, text: currentText, isLoading: false, streaming: true } 
                      : msg
                  )
                )
              }
              
              // 处理关键词
              if (data.keyword && data.keyword !== currentKeyword) {
                currentKeyword = data.keyword
                console.log('检测到关键词:', currentKeyword)
                
                // 根据关键词播放对应的Live2D动作
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
      console.error('Error sending message:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      const errorMsg = error instanceof Error ? error.message : '发送消息失败';
      setConnectionError(errorMsg);
      setMessages(prev => 
        prev.map(msg => 
          msg.id === loadingId 
            ? { ...msg, text: `错误: ${errorMsg}`, isLoading: false } 
            : msg
        )
      )
    } finally {
      setIsLoading(false)
      setLoadingMessageId(null)
    }
  }, [queueAndPlayAudio, resetAudioState, currentSessionId, refreshSessions, connectionStatus, checkConnection, connectionError])

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
      connectionStatus,
      connectionError,
      sendMessage, 
      clearChat, 
      createNewSession, 
      switchSession, 
      deleteSession, 
      refreshSessions,
      checkConnection
    }}>
      {children}
    </ChatContext.Provider>
  )
} 