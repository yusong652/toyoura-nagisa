import React, { createContext, useContext, useState, useCallback, ReactNode, useRef, useEffect } from 'react'
import { ConnectionStatus, ConnectionContextType, ToolConfirmationData } from '../../types/connection'
import GeolocationService from '../../utils/geolocation'
import {
  ConnectionManager,
  BrowserWebSocketAdapter,
  ConnectionState,
  type LocationData
} from '@aiNagisa/core'

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

/**
 * Map core ConnectionState to web ConnectionStatus
 */
const mapConnectionState = (state: ConnectionState): ConnectionStatus => {
  switch (state) {
    case ConnectionState.CONNECTED:
      return ConnectionStatus.CONNECTED
    case ConnectionState.CONNECTING:
    case ConnectionState.RECONNECTING:
      return ConnectionStatus.CONNECTING
    case ConnectionState.DISCONNECTED:
    case ConnectionState.DISCONNECTING:
      return ConnectionStatus.DISCONNECTED
    case ConnectionState.ERROR:
      return ConnectionStatus.ERROR
    default:
      return ConnectionStatus.DISCONNECTED
  }
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children }) => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.CONNECTING)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [pendingToolConfirmation, setPendingToolConfirmation] = useState<ToolConfirmationData | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)

  // Use ref for ConnectionManager instance
  const connectionManagerRef = useRef<ConnectionManager | null>(null)

  // WebSocket ref for compatibility (components may still access wsRef.current)
  const wsRef = useRef<WebSocket | null>(null)

  // Track if component is mounted to handle React StrictMode double-mounting
  const isMountedRef = useRef<boolean>(true)

  // Clean up on component unmount
  useEffect(() => {
    isMountedRef.current = true

    return () => {
      isMountedRef.current = false
      console.log("[ConnectionContext] Component unmounting, cleaning up...")

      if (connectionManagerRef.current) {
        connectionManagerRef.current.disconnect(1000, "Component unmount")
        connectionManagerRef.current = null
      }

      // Clear global references
      (window as any).__wsConnection = null
      wsRef.current = null
    }
  }, [])

  // Initialize ConnectionManager
  const initializeConnectionManager = useCallback(() => {
    if (connectionManagerRef.current) {
      return connectionManagerRef.current
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws"
    const wsHost = window.location.hostname
    const baseUrl = `${protocol}://${wsHost}:8000/ws/placeholder`

    const adapter = new BrowserWebSocketAdapter()
    const manager = new ConnectionManager(adapter, baseUrl, {
      maxReconnectAttempts: 5,
      reconnectInterval: 2000,
      enableHeartbeat: true,
      enableAutoReconnect: true
    })

    // Setup location request handler
    manager.setLocationRequestHandler(async (data: any): Promise<LocationData | null> => {
      console.log('[ConnectionContext] Received location request:', data)

      try {
        const geolocationService = GeolocationService.getInstance()

        if (!geolocationService.isServiceInitialized()) {
          await geolocationService.initialize()
        }

        const locationData = await geolocationService.requestLocation()

        if (locationData) {
          console.log('[ConnectionContext] Location data obtained:', locationData)
          return locationData
        } else {
          console.warn('[ConnectionContext] Unable to get location information')
          return null
        }
      } catch (error) {
        console.error('[ConnectionContext] Error handling location request:', error)
        return null
      }
    })

    // Setup event handlers
    manager.on('stateChanged', ({ newState }: { newState: ConnectionState }) => {
      if (!isMountedRef.current) return

      const status = mapConnectionState(newState)
      console.log(`[ConnectionContext] State changed: ${newState} -> ${status}`)
      setConnectionStatus(status)

      if (newState === ConnectionState.CONNECTED) {
        setConnectionError(null)
      }
    })

    manager.on('connected', () => {
      if (!isMountedRef.current) return
      console.log("[ConnectionContext] Connected to session")
      setConnectionStatus(ConnectionStatus.CONNECTED)
      setConnectionError(null)

      // Expose native WebSocket for ChatService compatibility
      const nativeWs = manager.getNativeWebSocket()
      if (nativeWs) {
        wsRef.current = nativeWs
        ;(window as any).__wsConnection = nativeWs
      }
    })

    manager.on('disconnected', ({ code, reason }: { code: number; reason: string }) => {
      if (!isMountedRef.current) return
      console.log(`[ConnectionContext] Disconnected: ${code} - ${reason}`)
      setConnectionStatus(ConnectionStatus.DISCONNECTED)
      wsRef.current = null
      ;(window as any).__wsConnection = null
    })

    manager.on('error', (error: Error) => {
      if (!isMountedRef.current) return
      console.error("[ConnectionContext] Connection error:", error)
      setConnectionStatus(ConnectionStatus.ERROR)
      setConnectionError(error.message)
    })

    manager.on('maxReconnectAttemptsReached', () => {
      if (!isMountedRef.current) return
      console.log("[ConnectionContext] Max reconnect attempts reached")
      setConnectionStatus(ConnectionStatus.ERROR)
      setConnectionError("Maximum reconnection attempts reached")
    })

    // Setup message handlers - dispatch CustomEvents for React components
    manager.on('tts_chunk', (data) => {
      window.dispatchEvent(new CustomEvent('websocket-tts-chunk', { detail: data }))
    })

    manager.on('status_update', (data) => {
      window.dispatchEvent(new CustomEvent('messageStatusUpdate', { detail: data }))
    })

    manager.on('message_create', (data) => {
      window.dispatchEvent(new CustomEvent('messageCreate', { detail: data }))
    })

    manager.on('streaming_update', (data) => {
      window.dispatchEvent(new CustomEvent('streamingUpdate', { detail: data }))
    })

    manager.on('title_update', (data) => {
      window.dispatchEvent(new CustomEvent('titleUpdate', { detail: data }))
    })

    manager.on('todo_update', (data) => {
      window.dispatchEvent(new CustomEvent('todoUpdate', { detail: data }))
    })

    manager.on('emotion_keyword', (data) => {
      window.dispatchEvent(new CustomEvent('emotionKeyword', { detail: data }))
    })

    manager.on('tool_confirmation_request', (data: ToolConfirmationData) => {
      console.log('[ConnectionContext] Received TOOL_CONFIRMATION_REQUEST', data)
      setPendingToolConfirmation(data)
      window.dispatchEvent(new CustomEvent('toolConfirmationRequest', { detail: data }))
    })

    manager.on('background_process_notification', (data) => {
      console.log('[ConnectionContext] Dispatching backgroundProcessNotification event:', data)
      window.dispatchEvent(new CustomEvent('backgroundProcessNotification', { detail: data }))
    })

    manager.on('message_saved', (data) => {
      console.log('[ConnectionContext] Dispatching messageSaved event:', data)
      window.dispatchEvent(new CustomEvent('messageSaved', { detail: data }))
    })

    connectionManagerRef.current = manager
    return manager
  }, [])

  // Check connection to backend
  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      setConnectionStatus(ConnectionStatus.CONNECTING)
      setConnectionError(null)

      const response = await fetch('/api/history/sessions', {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      })

      if (response.ok) {
        setConnectionStatus(ConnectionStatus.CONNECTED)
        return true
      } else {
        setConnectionStatus(ConnectionStatus.ERROR)
        setConnectionError(`Server returned error: ${response.status}`)
        return false
      }
    } catch (error) {
      console.error('Connection check failed:', error)
      setConnectionStatus(ConnectionStatus.DISCONNECTED)
      setConnectionError(error instanceof Error ? error.message : 'Unable to connect to server')
      return false
    }
  }, [])

  // Connect to specified session WebSocket
  const connectToSession = useCallback((sessionId: string) => {
    if (!sessionId) return

    if (!isMountedRef.current) {
      console.log(`[ConnectionContext] Component not mounted, skipping connection to ${sessionId}`)
      return
    }

    console.log(`[ConnectionContext] Connecting to session ${sessionId}`)
    setCurrentSessionId(sessionId)

    const manager = initializeConnectionManager()

    manager.connectToSession(sessionId).catch((error) => {
      console.error(`[ConnectionContext] Failed to connect to session ${sessionId}:`, error)
      if (isMountedRef.current) {
        setConnectionStatus(ConnectionStatus.ERROR)
        setConnectionError(error.message)
      }
    })
  }, [initializeConnectionManager])

  // Disconnect WebSocket connection
  const disconnect = useCallback(() => {
    console.log("[ConnectionContext] Manually disconnecting")
    setCurrentSessionId(null)

    if (connectionManagerRef.current) {
      connectionManagerRef.current.disconnect(1000, "Manual disconnect")
    }

    if (isMountedRef.current) {
      setConnectionStatus(ConnectionStatus.DISCONNECTED)
    }
  }, [])

  // Send WebSocket message
  const sendWebSocketMessage = useCallback((message: any) => {
    if (!connectionManagerRef.current) {
      console.warn('[ConnectionContext] ConnectionManager not initialized')
      return
    }

    if (!connectionManagerRef.current.isConnected()) {
      console.warn('[ConnectionContext] Not connected, cannot send message')
      return
    }

    connectionManagerRef.current.sendMessage(message).catch((error) => {
      console.error('[ConnectionContext] Failed to send message:', error)
    })
  }, [])

  // Wait for WebSocket connection to establish
  const waitForConnection = useCallback((timeout: number = 10000): Promise<boolean> => {
    return new Promise((resolve) => {
      if (connectionManagerRef.current?.isConnected()) {
        resolve(true)
        return
      }

      const checkConnection = () => {
        if (connectionManagerRef.current?.isConnected()) {
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

  // Register location request handler (legacy compatibility)
  const onLocationRequest = useCallback((_handler: (data: any) => void) => {
    console.warn('[ConnectionContext] onLocationRequest is deprecated, location handling is built-in')
    // Location handling is now built into ConnectionManager
    // This function is kept for compatibility but does nothing
  }, [])

  // Clear pending tool confirmation
  const clearPendingToolConfirmation = useCallback(() => {
    setPendingToolConfirmation(null)
  }, [])

  // Expose WebSocket and utilities for compatibility
  useEffect(() => {
    const manager = connectionManagerRef.current
    if (manager && manager.isConnected()) {
      // Expose native WebSocket for ChatService
      const nativeWs = manager.getNativeWebSocket()
      if (nativeWs) {
        wsRef.current = nativeWs
        ;(window as any).__wsConnection = nativeWs
      }
      ;(window as any).__waitForConnection = waitForConnection
    } else {
      ;(window as any).__wsConnection = null
    }
  }, [connectionStatus, waitForConnection])

  return (
    <ConnectionContext.Provider value={{
      connectionStatus,
      connectionError,
      sessionId: currentSessionId,
      wsRef, // Keep for compatibility, though deprecated
      connectToSession,
      disconnect,
      sendWebSocketMessage,
      onLocationRequest,
      checkConnection,
      waitForConnection,
      pendingToolConfirmation,
      clearPendingToolConfirmation
    }}>
      {children}
    </ConnectionContext.Provider>
  )
}
