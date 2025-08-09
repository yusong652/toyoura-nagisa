import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { ConnectionStatus } from '../../types/connection'
import { ChatSession, SessionContextType } from '../../types/session'
import { sessionService } from '../../services/api'
import { useConnection } from '../connection/ConnectionContext'
import { useTools } from '../tools/ToolsContext'

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
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ 
  children
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
      
      return newSessionId
    } catch (error) {
      console.error('Error in createNewSession:', error)
      throw error
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError, ttsEnabled, updateTtsEnabled])

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
      
      // SessionContext 不再负责加载消息，这个责任完全交给 ChatContext
      // 这样避免重复加载，职责更清晰
    } catch (error) {
      console.error('切换会话失败:', error)
      throw error
    }
  }, [connectionStatus, checkConnection, connectionError, ttsEnabled, updateTtsEnabled])

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

  return (
    <SessionContext.Provider value={{
      sessions,
      currentSessionId,
      sessionLoadAttempted,
      refreshSessions,
      createNewSession,
      switchSession,
      deleteSession,
      refreshTitle
    }}>
      {children}
    </SessionContext.Provider>
  )
}