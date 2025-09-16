import React, { createContext, useContext, useState, useCallback, ReactNode, useRef, useEffect } from 'react'
import { ConnectionStatus, ConnectionContextType } from '../../types/connection'
import GeolocationService from '../../utils/geolocation'

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined)

export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext)
  if (!context) {
    throw new Error('useConnection must be used within a ConnectionProvider')
  }
  return context
}


interface ConnectionProviderProps {
  children: ReactNode
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children }) => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.CONNECTING)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const locationRequestHandler = useRef<((data: any) => void) | null>(null)
  
  // 重连管理
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const currentSessionIdRef = useRef<string | null>(null)
  const maxReconnectAttempts = 5
  const baseReconnectDelay = 2000

  // 处理位置请求的函数
  const handleLocationRequest = useCallback(async (data: any, currentSessionId: string | null) => {
    console.log('收到位置请求:', data)
    
    try {
      // 获取地理位置服务实例
      const geolocationService = GeolocationService.getInstance()
      
      // 确保服务已初始化
      if (!geolocationService.isServiceInitialized()) {
        await geolocationService.initialize()
      }
      
      // 获取位置信息
      const locationData = await geolocationService.requestLocation()
      
      if (locationData) {
        // 通过WebSocket直接回复位置数据
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const locationResponse = {
            type: 'LOCATION_RESPONSE',
            session_id: currentSessionId,
            location_data: locationData,
            timestamp: new Date().toISOString()
          }
          
          wsRef.current.send(JSON.stringify(locationResponse))
          console.log('位置信息已通过WebSocket发送到后端:', locationData)
        } else {
          console.warn('WebSocket连接不可用，无法发送位置信息')
        }
      } else {
        console.warn('无法获取位置信息')
        
        // 发送位置获取失败的响应
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const errorResponse = {
            type: 'LOCATION_RESPONSE',
            session_id: currentSessionId,
            error: 'Failed to get location',
            timestamp: new Date().toISOString()
          }
          
          wsRef.current.send(JSON.stringify(errorResponse))
        }
      }
    } catch (error) {
      console.error('处理位置请求时出错:', error)
    }
  }, [])

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

  // Reconnect logic is now inline in onclose to avoid circular dependencies

  // 连接到指定会话的WebSocket
  const connectToSession = useCallback((sessionId: string) => {
    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Close previous ws if any
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch (_) {}
      wsRef.current = null
    }

    if (!sessionId) return

    // Store current session ID for reconnection
    currentSessionIdRef.current = sessionId

    const protocol = window.location.protocol === "https:" ? "wss" : "ws"
    // WebSocket 连接应该指向后端服务器端口 8000，而不是前端 Vite 端口 5173
    const wsHost = window.location.hostname
    const ws = new WebSocket(`${protocol}://${wsHost}:8000/ws/${sessionId}`)
    wsRef.current = ws

    ws.onopen = () => {
      try {
        console.log("[WebSocket] connected for session", sessionId)
        setConnectionStatus(ConnectionStatus.CONNECTED)
        setConnectionError(null)

        // Reset reconnect attempts on successful connection
        if (reconnectAttemptsRef.current !== undefined) {
          reconnectAttemptsRef.current = 0
        }

        // Expose WebSocket connection globally for services
        (window as any).__wsConnection = ws
      } catch (error) {
        console.error("[WebSocket] Error in onopen handler:", error)
      }
    }

    ws.onclose = (event) => {
      console.log("[WebSocket] closed for session", sessionId, "Code:", event.code, "Reason:", event.reason)
      setConnectionStatus(ConnectionStatus.DISCONNECTED)

      // Clear global WebSocket reference
      (window as any).__wsConnection = null

      // Only attempt reconnect if it wasn't a clean close and we have a session ID
      if (event.code !== 1000 && currentSessionIdRef.current) {
        console.log("[WebSocket] Connection lost, attempting to reconnect...")

        // Inline reconnect logic to avoid circular dependency
        if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log("[WebSocket] Max reconnect attempts reached")
          setConnectionStatus(ConnectionStatus.ERROR)
          setConnectionError("达到最大重连次数")
          return
        }

        reconnectAttemptsRef.current++
        const delay = Math.min(baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current - 1), 30000)

        console.log(`[WebSocket] Attempting reconnect ${reconnectAttemptsRef.current}/${maxReconnectAttempts} after ${delay}ms`)

        reconnectTimeoutRef.current = setTimeout(() => {
          connectToSession(sessionId)
        }, delay)
      }
    }

    ws.onerror = (e) => {
      console.error("[WebSocket] error", e)
      setConnectionStatus(ConnectionStatus.ERROR)
      setConnectionError("WebSocket连接错误")
    }
    
    // Handle incoming WebSocket messages
    ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log("[WebSocket] received message:", data)
        
        // Handle heartbeat messages
        if (data.type === 'HEARTBEAT') {
          console.log('WebSocket received heartbeat, sending ACK')
          const heartbeatAck = {
            type: 'HEARTBEAT_ACK',
            timestamp: new Date().toISOString()
          }
          ws.send(JSON.stringify(heartbeatAck))
        }
        
        // Handle TTS chunks - dispatch custom events for TTS processors
        if (data.type === 'TTS_CHUNK') {
          // Dispatch custom event for existing TTS processors to handle
          const ttsEvent = new CustomEvent('websocket-tts-chunk', {
            detail: {
              text: data.text,
              audio: data.audio,
              index: data.index,
              is_final: data.is_final,
              message_id: data.message_id,
              engine_status: data.engine_status,
              error: data.error,
              processing_time: data.processing_time
            }
          })

          window.dispatchEvent(ttsEvent)
        }

        // Handle location requests
        if (data.type === 'LOCATION_REQUEST') {
          console.log('WebSocket received location request')
          await handleLocationRequest(data, sessionId)
        }

        // Call external location request handler if registered
        if (locationRequestHandler.current && data.type === 'LOCATION_REQUEST') {
          locationRequestHandler.current(data)
        }
        
        // Handle message status updates
        if (data.type === 'STATUS_UPDATE') {
          // Dispatch custom event for message status updates
          window.dispatchEvent(new CustomEvent('messageStatusUpdate', {
            detail: {
              messageId: data.message_id,
              status: data.status,
              errorMessage: data.error_message
            }
          }))
        }
        
        // Handle tool use notifications
        if (data.type === 'NAGISA_IS_USING_TOOL') {
          
          // Dispatch custom event for other components to listen to
          window.dispatchEvent(new CustomEvent('toolUseStarted', { 
            detail: data 
          }))
        }
        
        if (data.type === 'NAGISA_TOOL_USE_CONCLUDED') {

          // Dispatch custom event for other components to listen to
          window.dispatchEvent(new CustomEvent('toolUseConcluded', {
            detail: data
          }))
        }

        // Handle message creation requests
        if (data.type === 'MESSAGE_CREATE') {
          // Dispatch custom event for message creation
          window.dispatchEvent(new CustomEvent('messageCreate', {
            detail: {
              messageId: data.message_id,
              sender: data.sender,
              initialText: data.initial_text || '',
              streaming: data.streaming || true
            }
          }))
        }

        // Handle emotion keyword notifications
        if (data.type === 'EMOTION_KEYWORD') {
          // Dispatch custom event for keyword handling (Live2D animations)
          window.dispatchEvent(new CustomEvent('emotionKeyword', {
            detail: data
          }))
        }
      } catch (error) {
        console.error("[WebSocket] failed to parse message:", error)
      }
    }
  }, [handleLocationRequest, setConnectionStatus, setConnectionError])

  // 断开WebSocket连接
  const disconnect = useCallback(() => {
    // Clear reconnection attempts when manually disconnecting
    currentSessionIdRef.current = null
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      try {
        wsRef.current.close(1000, "Manual disconnect") // Clean close
      } catch (_) {}
      wsRef.current = null
    }
    setConnectionStatus(ConnectionStatus.DISCONNECTED)
  }, [])

  // 发送WebSocket消息
  const sendWebSocketMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }, [])

  // 等待WebSocket连接建立
  const waitForConnection = useCallback((timeout: number = 10000): Promise<boolean> => {
    return new Promise((resolve) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        resolve(true)
        return
      }

      const checkConnection = () => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          resolve(true)
        } else if (connectionStatus === ConnectionStatus.ERROR ||
                   connectionStatus === ConnectionStatus.DISCONNECTED) {
          resolve(false)
        } else {
          setTimeout(checkConnection, 100)
        }
      }

      setTimeout(() => resolve(false), timeout)
      checkConnection()
    })
  }, [connectionStatus])

  // 注册位置请求处理器
  const onLocationRequest = useCallback((handler: (data: any) => void) => {
    locationRequestHandler.current = handler
  }, [])

  // Expose WebSocket connection globally for services
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Expose WebSocket connection for ChatService
      (window as any).__wsConnection = wsRef.current
    } else {
      (window as any).__wsConnection = null
    }

    // Expose waitForConnection method
    (window as any).__waitForConnection = waitForConnection
  }, [connectionStatus, waitForConnection])

  // Handle requests for WebSocket connection
  useEffect(() => {
    const handleConnectionRequest = () => {
      return wsRef.current
    }

    window.addEventListener('getWebSocketConnection', handleConnectionRequest)

    return () => {
      window.removeEventListener('getWebSocketConnection', handleConnectionRequest)
    }
  }, [])

  // 清理WebSocket连接
  useEffect(() => {
    return () => {
      // Clear any pending reconnect timeouts
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }

      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (_) {}
      }

      // Clean up global reference
      (window as any).__wsConnection = null
    }
  }, [])

  return (
    <ConnectionContext.Provider value={{
      connectionStatus,
      connectionError,
      wsRef,
      connectToSession,
      disconnect,
      sendWebSocketMessage,
      onLocationRequest,
      checkConnection,
      waitForConnection
    }}>
      {children}
    </ConnectionContext.Provider>
  )
}