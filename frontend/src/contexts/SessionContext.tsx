import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { ChatSession, ConnectionStatus, Message, FileData, MessageStatus } from '../types/chat'
import { sessionService } from '../services/api'
import { useConnection } from './ConnectionContext'
import { useTools } from './ToolsContext'

export interface SessionContextType {
  // Session state
  sessions: ChatSession[]
  currentSessionId: string | null
  sessionLoadAttempted: boolean

  // Session operations
  refreshSessions: () => Promise<ChatSession[]>
  createNewSession: (name?: string) => Promise<string>
  switchSession: (sessionId: string) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  refreshTitle: (sessionId: string) => Promise<void>

  // Session message operations
  onSessionMessagesLoaded: (messages: Message[]) => void
}

const SessionContext = createContext<SessionContextType | undefined>(undefined)

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider')
  }
  return context
}

interface SessionProviderProps {
  children: ReactNode
  onSessionMessagesLoaded?: (messages: Message[]) => void
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ 
  children, 
  onSessionMessagesLoaded 
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [sessionLoadAttempted, setSessionLoadAttempted] = useState(false)
  
  const { 
    connectionStatus, 
    connectionError, 
    connectToSession, 
    checkConnection 
  } = useConnection()
  const { ttsEnabled, updateTtsEnabled } = useTools()

  // 刷新会话列表
  const refreshSessions = useCallback(async (): Promise<ChatSession[]> => {
    try {
      const data = await sessionService.getSessions()
      setSessions(data)
      return data
    } catch (error) {
      console.error('获取会话列表失败:', error)
      throw error
    }
  }, [])

  // 创建新会话
  const createNewSession = useCallback(async (name?: string): Promise<string> => {
    console.log('createNewSession called with name:', name)
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      console.log('Checking connection...')
      const canConnect = await checkConnection()
      if (!canConnect) {
        console.error('Connection check failed:', connectionError)
        throw new Error(connectionError || "无法连接到服务器，请重试。")
      }
    }
    try {
      console.log('Sending create session request...')
      const data = await sessionService.createSession(name)
      console.log('Create session response:', data)
      const newSessionId = data.session_id
      
      localStorage.setItem('session_id', newSessionId)
      setCurrentSessionId(newSessionId)

      // 同步 TTS 状态到后端
      try {
        await updateTtsEnabled(ttsEnabled)
      } catch (error) {
        console.error('同步 TTS 状态失败:', error)
      }

      await refreshSessions()
      
      // 通知外部组件新会话已创建，消息列表应为空
      if (onSessionMessagesLoaded) {
        onSessionMessagesLoaded([])
      }
      
      return newSessionId
    } catch (error) {
      console.error('Error in createNewSession:', error)
      throw error
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError, ttsEnabled, updateTtsEnabled, onSessionMessagesLoaded])

  // 切换会话
  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection()
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。")
      }
    }
    try {
      await sessionService.switchSession(sessionId)
      
      localStorage.setItem('session_id', sessionId)
      setCurrentSessionId(sessionId)

      // 同步 TTS 状态到后端
      try {
        await updateTtsEnabled(ttsEnabled)
      } catch (error) {
        console.error('同步 TTS 状态失败:', error)
      }
      
      const historyData = await sessionService.getSessionHistory(sessionId)
      if (!historyData.history || !Array.isArray(historyData.history)) {
        console.error('Invalid history data format:', historyData)
        if (onSessionMessagesLoaded) {
          onSessionMessagesLoaded([])
        }
        return
      }

      const convertedMessages: Message[] = historyData.history
        .filter((msg: any) => {
          // 只保留真正的用户发言、AI文本和图片消息
          if (msg.role === 'user' && !msg.tool_request) return true
          if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) return true
          if (msg.role === 'image') return true
          return false
        })
        .map((msg: any): Message | null => {
          // sender 判断更精确
          let sender: 'user' | 'bot'
          if (msg.role === 'user' && !msg.tool_request) {
            sender = 'user'
          } else if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) {
            sender = 'bot'
          } else if (msg.role === 'image') {
            sender = 'bot'  // 图片消息也作为bot的消息显示
          } else {
            console.warn('Unexpected message format:', msg)
            return null
          }

          let text = ''
          let files: FileData[] = []
          
          // 处理消息内容
          if (msg.role === 'image') {
            // 处理图片消息
            text = msg.content || ''
            files.push({
              name: 'generated_image',
              type: 'image/png',
              data: `/api/images/${msg.image_path}`  // 通过API路由访问图片
            })
          } else if (typeof msg.content === 'string') {
            text = msg.content
          } else if (Array.isArray(msg.content)) {
            // 合并所有文本内容
            const textContents = msg.content
              .filter((item: any) => item.text)
              .map((item: any) => item.text)
            text = textContents.join('\n')
            
            // 处理所有文件
            msg.content.forEach((item: any) => {
              if (item.inline_data) {
                files.push({
                  name: `image_${files.length + 1}`,
                  type: item.inline_data.mime_type,
                  data: `data:${item.inline_data.mime_type};base64,${item.inline_data.data}`
                })
              }
            })
          } else {
            console.warn('Invalid message content format:', msg.content)
            text = '消息格式错误'
          }

          // 处理工具状态
          let toolState = undefined
          if (msg.tool_state) {
            toolState = {
              isUsingTool: msg.tool_state.is_using_tool || false,
              toolName: msg.tool_state.tool_name,
              action: msg.tool_state.action
            }
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
            toolState
          }
        })
        .filter((msg: Message | null): msg is Message => msg !== null)

      // 通知外部组件会话消息已加载
      if (onSessionMessagesLoaded) {
        onSessionMessagesLoaded(convertedMessages)
      }
    } catch (error) {
      console.error('切换会话失败:', error)
      throw error
    }
  }, [connectionStatus, checkConnection, connectionError, ttsEnabled, updateTtsEnabled, onSessionMessagesLoaded])

  // 删除会话
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection()
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。")
      }
    }
    try {
      await sessionService.deleteSession(sessionId)

      // 用最新的 sessions 判断
      const latestSessions = await refreshSessions()

      if (sessionId === currentSessionId) {
        if (latestSessions.length > 0) {
          await switchSession(latestSessions[0].id)
        } else {
          await createNewSession()
        }
      }

    } catch (error) {
      console.error('删除会话失败:', error)
      throw error
    }
  }, [currentSessionId, createNewSession, refreshSessions, switchSession, connectionStatus, checkConnection, connectionError])

  // 刷新标题方法
  const refreshTitle = useCallback(async (sessionId: string): Promise<void> => {
    try {
      if (!sessionId) {
        throw new Error('会话ID不能为空')
      }

      const data = await sessionService.generateTitle(sessionId)

      // 如果成功生成了新标题，更新会话列表
      if (data.success && data.title) {
        // 更新本地状态中的会话标题
        setSessions(prevSessions => 
          prevSessions.map(session => 
            session.id === sessionId 
              ? { ...session, name: data.title }
              : session
          )
        )
      }
    } catch (error) {
      console.error('刷新标题失败:', error)
      throw error
    }
  }, [])

  // 初始化 Effect: ComponentDidMount
  useEffect(() => {
    const initLoad = async () => {
      // Attempt to establish connection and load initial data
      const connected = await checkConnection()
      if (!connected) {
        setSessionLoadAttempted(true) // Mark that an initial load attempt failed due to connection
        return
      }

      // Connection successful, now try to load session list and then the active session
      try {
        await refreshSessions() // Load all session details first

        const storedSessionId = localStorage.getItem('session_id')
        if (storedSessionId) {
          try {
            await switchSession(storedSessionId) // This loads messages for the session
            setSessionLoadAttempted(false) // Successfully loaded a session
          } catch (switchError) {
            console.error('初始化时无法切换到已存储会话，尝试创建新会话:', switchError)
            if (connectionStatus === ConnectionStatus.CONNECTED) {
              try {
                await createNewSession() // This loads messages for new session & refreshes list
                setSessionLoadAttempted(false) // Successfully created a new session
              } catch (createError) {
                console.error('初始化时创建新会话失败（切换会话后）:', createError)
                setSessionLoadAttempted(true) // Failed to establish a session
              }
            } else {
              setSessionLoadAttempted(true) // Connection lost during switchSession attempt
            }
          }
        } else {
          // No stored session, create a new one
          try {
            await createNewSession()
            setSessionLoadAttempted(false) // Successfully created a new session
          } catch (createError) {
            console.error('初始化时创建新会话失败（无存储ID）:', createError)
            setSessionLoadAttempted(true) // Failed to establish a session
          }
        }
      } catch (refreshError) {
        // Error from refreshSessions()
        console.error('初始化时加载会话列表失败:', refreshError)
        setSessionLoadAttempted(true) // Mark that the load was attempted and failed
      }
    }

    initLoad()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run only once on mount

  // Connect to WebSocket when session changes
  useEffect(() => {
    if (currentSessionId) {
      connectToSession(currentSessionId)
    }
  }, [currentSessionId, connectToSession])

  // 尝试在重新连接后加载会话
  useEffect(() => {
    const loadSessionOnReconnect = async () => {
      if (connectionStatus === ConnectionStatus.CONNECTED && sessionLoadAttempted && !currentSessionId) {
        console.log("检测到重新连接，尝试加载/刷新会话...")
        setSessionLoadAttempted(false) // We are attempting to load now

        try {
          await refreshSessions() // Load all session details first

          const storedSessionId = localStorage.getItem('session_id')
          if (storedSessionId) {
            try {
              await switchSession(storedSessionId)
              // Successfully loaded session on reconnect
            } catch (switchError) {
              console.error('重新连接后无法切换到已存储会话，尝试创建新会话:', switchError)
              if (connectionStatus === ConnectionStatus.CONNECTED) {
                try {
                  await createNewSession()
                } catch (createError) {
                  console.error('重新连接后创建新会话也失败（切换会话后）:', createError)
                  setSessionLoadAttempted(true) // Mark failed attempt
                }
              } else {
                 setSessionLoadAttempted(true) // Connection lost during switch
              }
            }
          } else {
            // No stored session, create a new one
            try {
              await createNewSession()
            } catch (createError) {
              console.error('重新连接后创建新会话失败（无存储ID）:', createError)
              setSessionLoadAttempted(true) // Mark failed attempt
            }
          }
        } catch (refreshError) {
          // Error from refreshSessions() during reconnect
          console.error('重新连接后加载会话列表失败:', refreshError)
          setSessionLoadAttempted(true) // Mark failed attempt so it can retry if connection cycles
        }
      }
    }

    loadSessionOnReconnect()
  }, [connectionStatus, sessionLoadAttempted, currentSessionId, refreshSessions, switchSession, createNewSession])

  const onSessionMessagesLoadedCallback = useCallback((messages: Message[]) => {
    if (onSessionMessagesLoaded) {
      onSessionMessagesLoaded(messages)
    }
  }, [onSessionMessagesLoaded])

  return (
    <SessionContext.Provider value={{
      sessions,
      currentSessionId,
      sessionLoadAttempted,
      refreshSessions,
      createNewSession,
      switchSession,
      deleteSession,
      refreshTitle,
      onSessionMessagesLoaded: onSessionMessagesLoadedCallback
    }}>
      {children}
    </SessionContext.Provider>
  )
}