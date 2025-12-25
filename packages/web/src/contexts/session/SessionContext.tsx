import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react'
import { ConnectionStatus } from '../../types/connection'
import {
  ChatSession,
  SessionContextType,
  TokenUsage,
  SessionManager,
  SessionEvent,
  LocalStorageAdapter,
  sessionService
} from '@toyoura-nagisa/core'
import { useConnection } from '../connection/ConnectionContext'

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
  // React state
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

  // Create SessionManager instance
  const sessionManagerRef = useRef<SessionManager>()
  if (!sessionManagerRef.current) {
    sessionManagerRef.current = new SessionManager(
      sessionService,
      new LocalStorageAdapter()
    )
  }
  const sessionManager = sessionManagerRef.current

  // Subscribe to SessionManager events
  useEffect(() => {
    // Session created event
    sessionManager.on(SessionEvent.SESSION_CREATED, ({ sessionId }) => {
      setCurrentSessionId(sessionId)
      setSessionTokenUsage(null) // New session has no token usage
    })

    // Session switched event
    sessionManager.on(SessionEvent.SESSION_SWITCHED, ({ sessionId }) => {
      setCurrentSessionId(sessionId)
    })

    // Sessions loaded event
    sessionManager.on(SessionEvent.SESSIONS_LOADED, ({ sessions: loadedSessions }) => {
      setSessions(loadedSessions)
    })

    // Token usage updated event
    sessionManager.on(SessionEvent.TOKEN_USAGE_UPDATED, ({ usage }) => {
      setSessionTokenUsage(usage)
    })

    // Session deleted event
    sessionManager.on(SessionEvent.SESSION_DELETED, ({ sessionId }) => {
      // SessionManager will handle switching to another session
      console.log(`Session ${sessionId} deleted`)
    })

    return () => {
      sessionManager.removeAllListeners()
    }
  }, [sessionManager])

  // 刷新会话列表
  const refreshSessions = useCallback(async (): Promise<ChatSession[]> => {
    try {
      return await sessionManager.loadSessions()
    } catch (error) {
      console.error('获取会话列表失败:', error)
      throw error
    }
  }, [sessionManager])

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
      console.log('Creating session via SessionManager...')
      const newSessionId = await sessionManager.createSession(name)
      console.log('Session created:', newSessionId)

      return newSessionId
    } catch (error) {
      console.error('Error in createNewSession:', error)
      throw error
    }
  }, [sessionManager, connectionStatus, checkConnection, connectionError])


  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection()
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。")
      }
    }
    try {
      await sessionManager.switchSession(sessionId)
    } catch (error) {
      console.error('切换会话失败:', error)
      throw error
    }
  }, [sessionManager, connectionStatus, checkConnection, connectionError])


  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection()
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。")
      }
    }
    try {
      // SessionManager will handle automatic session switching
      await sessionManager.deleteSession(sessionId)
    } catch (error) {
      console.error('删除会话失败:', error)
      throw error
    }
  }, [sessionManager, connectionStatus, checkConnection, connectionError])


  const refreshTitle = useCallback(async (sessionId: string): Promise<void> => {
    try {
      if (!sessionId) {
        throw new Error('会话ID不能为空')
      }

      await sessionManager.refreshTitle(sessionId)
    } catch (error) {
      console.error('刷新标题失败:', error)
      throw error
    }
  }, [sessionManager])

  // Initialize SessionManager and load sessions
  useEffect(() => {
    const initLoad = async () => {
      // Attempt to establish connection
      const connected = await checkConnection()
      if (!connected) {
        setSessionLoadAttempted(true)
        return
      }

      try {
        // Initialize SessionManager (loads current session ID from storage)
        await sessionManager.initialize()

        // Get stored session ID from SessionManager
        const storedSessionId = sessionManager.getCurrentSessionId()

        if (storedSessionId) {
          try {
            await switchSession(storedSessionId)
            setSessionLoadAttempted(false)
          } catch (switchError) {
            console.error('初始化时无法切换到已存储会话，尝试创建新会话:', switchError)
            if (connectionStatus === ConnectionStatus.CONNECTED) {
              try {
                await createNewSession()
                setSessionLoadAttempted(false)
              } catch (createError) {
                console.error('初始化时创建新会话失败:', createError)
                setSessionLoadAttempted(true)
              }
            } else {
              setSessionLoadAttempted(true)
            }
          }
        } else {
          // No stored session, create a new one
          try {
            await createNewSession()
            setSessionLoadAttempted(false)
          } catch (createError) {
            console.error('初始化时创建新会话失败:', createError)
            setSessionLoadAttempted(true)
          }
        }
      } catch (error) {
        console.error('初始化SessionManager失败:', error)
        setSessionLoadAttempted(true)
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

  // Reload sessions on reconnect
  useEffect(() => {
    const loadSessionOnReconnect = async () => {
      if (connectionStatus === ConnectionStatus.CONNECTED && sessionLoadAttempted && !currentSessionId) {
        setSessionLoadAttempted(false)

        try {
          await refreshSessions()

          const storedSessionId = sessionManager.getCurrentSessionId()
          if (storedSessionId) {
            try {
              await switchSession(storedSessionId)
            } catch (switchError) {
              console.error('重新连接后无法切换到已存储会话，尝试创建新会话:', switchError)
              if (connectionStatus === ConnectionStatus.CONNECTED) {
                try {
                  await createNewSession()
                } catch (createError) {
                  console.error('重新连接后创建新会话失败:', createError)
                  setSessionLoadAttempted(true)
                }
              } else {
                setSessionLoadAttempted(true)
              }
            }
          } else {
            try {
              await createNewSession()
            } catch (createError) {
              console.error('重新连接后创建新会话失败:', createError)
              setSessionLoadAttempted(true)
            }
          }
        } catch (refreshError) {
          console.error('重新连接后加载会话列表失败:', refreshError)
          setSessionLoadAttempted(true)
        }
      }
    }

    loadSessionOnReconnect()
  }, [connectionStatus, sessionLoadAttempted, currentSessionId, sessionManager, refreshSessions, switchSession, createNewSession])

  // Listen for WebSocket streaming updates to update token usage in real-time
  useEffect(() => {
    const handleStreamingUpdate = (event: CustomEvent) => {
      const { usage } = event.detail
      if (usage) {
        // Update token usage via SessionManager
        sessionManager.updateTokenUsage(usage)
      }
    }

    window.addEventListener('streamingUpdate', handleStreamingUpdate as EventListener)

    return () => {
      window.removeEventListener('streamingUpdate', handleStreamingUpdate as EventListener)
    }
  }, [sessionManager])

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