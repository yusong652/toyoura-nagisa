import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { ConnectionStatus } from '../../types/connection'
import { ChatSession, SessionContextType, TokenUsage } from '@aiNagisa/core'
import { sessionService } from '@aiNagisa/core'
import { useConnection } from '../connection/ConnectionContext'
import { useTtsEnable } from '../audio/TtsEnableContext'

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
  const [sessionTokenUsage, setSessionTokenUsage] = useState<TokenUsage | null>(null)

  const {
    connectionStatus,
    connectionError,
    connectToSession,
    checkConnection
  } = useConnection()
  const { ttsEnabled, updateTTSEnabled } = useTtsEnable()

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

      // New session has no token usage yet
      setSessionTokenUsage(null)

      // 同步 TTS 状态到后端
      try {
        await updateTTSEnabled(ttsEnabled)
      } catch (error) {
        console.error('同步 TTS 状态失败:', error)
      }

      await refreshSessions()

      return newSessionId
    } catch (error) {
      console.error('Error in createNewSession:', error)
      throw error
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError, ttsEnabled, updateTTSEnabled])


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

      // Load token usage for this session
      try {
        const usage = await sessionService.getTokenUsage(sessionId)
        setSessionTokenUsage(usage)
      } catch (error) {
        console.error('Failed to load token usage:', error)
        setSessionTokenUsage(null)
      }

      try {
        await updateTTSEnabled(ttsEnabled)
      } catch (error) {
        console.error('同步 TTS 状态失败:', error)
      }

    } catch (error) {
      console.error('切换会话失败:', error)
      throw error
    }
  }, [connectionStatus, checkConnection, connectionError, ttsEnabled, updateTTSEnabled])


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


  const refreshTitle = useCallback(async (sessionId: string): Promise<void> => {
    try {
      if (!sessionId) {
        throw new Error('会话ID不能为空')
      }

      const data = await sessionService.generateTitle(sessionId)

      if (data.success && data.title) {
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
  }, [currentSessionId]) // Remove connectToSession from dependencies to prevent unnecessary reconnects

  useEffect(() => {
    const loadSessionOnReconnect = async () => {
      if (connectionStatus === ConnectionStatus.CONNECTED && sessionLoadAttempted && !currentSessionId) {
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

  // Listen for WebSocket streaming updates to update token usage in real-time
  useEffect(() => {
    const handleStreamingUpdate = (event: CustomEvent) => {
      const { usage } = event.detail
      if (usage) {
        setSessionTokenUsage(usage)
      }
    }

    window.addEventListener('streamingUpdate', handleStreamingUpdate as EventListener)

    return () => {
      window.removeEventListener('streamingUpdate', handleStreamingUpdate as EventListener)
    }
  }, [])

  return (
    <SessionContext.Provider value={{
      sessions,
      currentSessionId,
      sessionLoadAttempted,
      sessionTokenUsage,
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