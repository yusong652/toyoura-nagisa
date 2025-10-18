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

  // Store pending bash confirmation requests for late-mounting components
  const pendingConfirmationRef = useRef<any | null>(null)

  // Reconnection management
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const currentSessionIdRef = useRef<string | null>(null)
  const maxReconnectAttempts = 5

  // Clean up WebSocket connections on component unmount
  useEffect(() => {
    return () => {
      // Cleanup function: executed on component unmount or hot reload
      console.log("[WebSocket] Component unmounting, cleaning up connections...")
      if (wsRef.current) {
        try {
          wsRef.current.close(1000, "Component unmount")
        } catch (error) {
          console.error("[WebSocket] Error closing connection on unmount:", error)
        }
        wsRef.current = null
      }
      // Clear global references
      (window as any).__wsConnection = null
      // Clear reconnection timers
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [])
  const baseReconnectDelay = 2000

  // Function to handle location requests
  const handleLocationRequest = useCallback(async (data: any, currentSessionId: string | null) => {
    console.log('Received location request:', data)

    try {
      // Get geolocation service instance
      const geolocationService = GeolocationService.getInstance()
      
      // Ensure service is initialized
      if (!geolocationService.isServiceInitialized()) {
        await geolocationService.initialize()
      }

      // Get location information
      const locationData = await geolocationService.requestLocation()

      if (locationData) {
        // Reply location data directly via WebSocket - align with HEARTBEAT_ACK pattern
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const locationResponse = {
            type: 'LOCATION_RESPONSE',
            session_id: currentSessionId,
            request_id: data.request_id, // Include request_id for Future correlation
            location_data: locationData,
            timestamp: new Date().toISOString()
          }

          wsRef.current.send(JSON.stringify(locationResponse))
          console.log('[LOCATION] Location response sent via wsRef.current:', locationData)
        } else {
          console.warn('[LOCATION] wsRef.current is not available or not open, cannot send location response')
        }
      } else {
        console.warn('[LOCATION] Unable to get location information')

        // Send location acquisition failure response - align with HEARTBEAT_ACK pattern
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const errorResponse = {
            type: 'LOCATION_RESPONSE',
            session_id: currentSessionId,
            request_id: data.request_id, // Include request_id for Future correlation
            error: 'Failed to get location',
            timestamp: new Date().toISOString()
          }

          wsRef.current.send(JSON.stringify(errorResponse))
          console.log('[LOCATION] Location error response sent via wsRef.current')
        } else {
          console.warn('[LOCATION] wsRef.current is not available or not open, cannot send error response')
        }
      }
    } catch (error) {
      console.error('Error handling location request:', error)
    }
  }, [])

  // Check connection to backend
  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      setConnectionStatus(() => ConnectionStatus.CONNECTING)
      setConnectionError(() => null)

      const response = await fetch('/api/history/sessions', {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      })
      
      if (response.ok) {
        setConnectionStatus(() => ConnectionStatus.CONNECTED)
        return true
      } else {
        setConnectionStatus(() => ConnectionStatus.ERROR)
        setConnectionError(() => `Server returned error: ${response.status}`)
        return false
      }
    } catch (error) {
      console.error('Connection check failed:', error)
      setConnectionStatus(() => ConnectionStatus.DISCONNECTED)
      setConnectionError(() => error instanceof Error ? error.message : 'Unable to connect to server')
      return false
    }
  }, [])

  // Reconnect logic is now inline in onclose to avoid circular dependencies

  // Connect to specified session WebSocket
  const connectToSession = useCallback((sessionId: string) => {
    if (!sessionId) return

    // If we're already connected to this session, don't create another connection
    if (currentSessionIdRef.current === sessionId &&
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN) {
      console.log(`[WebSocket] Already connected to session ${sessionId}, skipping`)
      return
    }

    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Store current session ID for reconnection
    currentSessionIdRef.current = sessionId

    // Close previous ws if any
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, "Switching session")
      } catch (_) {}
      wsRef.current = null
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws"
    // WebSocket connection should point to backend server port 8000, not frontend Vite port 5173
    const wsHost = window.location.hostname
    const ws = new WebSocket(`${protocol}://${wsHost}:8000/ws/${sessionId}`)
    wsRef.current = ws

    ws.onopen = () => {
      try {
        console.log("[WebSocket] connected for session", sessionId)
        setConnectionStatus(() => ConnectionStatus.CONNECTED)
        setConnectionError(() => null)

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
      // Use more stable state update method
      try {
        setConnectionStatus(() => ConnectionStatus.DISCONNECTED)
      } catch (error) {
        console.error("[WebSocket] Error updating connection status:", error)
      }

      // Clear global WebSocket reference
      (window as any).__wsConnection = null

      // Only attempt reconnect if:
      // 1. It wasn't a clean close (code !== 1000)
      // 2. This session is still the current session
      // 3. We have a valid session ID
      if (event.code !== 1000 && currentSessionIdRef.current === sessionId && sessionId) {
        console.log("[WebSocket] Connection lost for current session, attempting to reconnect...")

        // Inline reconnect logic to avoid circular dependency
        if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log("[WebSocket] Max reconnect attempts reached")
          setConnectionStatus(() => ConnectionStatus.ERROR)
          setConnectionError(() => "Maximum reconnection attempts reached")
          return
        }

        reconnectAttemptsRef.current++
        const delay = Math.min(baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current - 1), 30000)

        console.log(`[WebSocket] Attempting reconnect ${reconnectAttemptsRef.current}/${maxReconnectAttempts} after ${delay}ms`)

        reconnectTimeoutRef.current = setTimeout(async () => {
          // Double check this is still the current session before reconnecting
          if (currentSessionIdRef.current !== sessionId) {
            console.log(`[WebSocket] Session changed during reconnect delay, aborting reconnect for ${sessionId}`)
            return
          }

          // Validate session still exists before reconnecting
          try {
            const response = await fetch(`/api/history/${sessionId}`)
            if (response.ok) {
              connectToSession(sessionId)
            } else {
              console.log(`[WebSocket] Session ${sessionId} no longer exists, stopping reconnection`)
              currentSessionIdRef.current = null
              setConnectionStatus(() => ConnectionStatus.DISCONNECTED)
            }
          } catch (error) {
            console.error(`[WebSocket] Error validating session ${sessionId}:`, error)
            // If we can't validate, try once more then stop
            if (reconnectAttemptsRef.current >= maxReconnectAttempts - 1) {
              console.log("[WebSocket] Cannot validate session, stopping reconnection")
              currentSessionIdRef.current = null
              setConnectionStatus(() => ConnectionStatus.ERROR)
            } else {
              connectToSession(sessionId)
            }
          }
        }, delay)
      } else if (currentSessionIdRef.current !== sessionId) {
        console.log(`[WebSocket] Connection closed for old session ${sessionId}, not reconnecting (current: ${currentSessionIdRef.current})`)
      }
    }

    ws.onerror = (e) => {
      console.error("[WebSocket] error", e)
      setConnectionStatus(() => ConnectionStatus.ERROR)
      setConnectionError(() => "WebSocket connection error")
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
          // Use wsRef.current instead of ws to ensure we're using the correct WebSocket instance
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(heartbeatAck))
            console.log('HEARTBEAT_ACK sent via wsRef.current')
          } else {
            console.warn('wsRef.current is not available or not open, cannot send HEARTBEAT_ACK')
          }
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
          console.log('[LOCATION] WebSocket received location request:', data)
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
              role: data.role,
              initialText: data.initial_text || '',
              streaming: data.streaming || true
            }
          }))
        }

        // Handle title update notifications
        if (data.type === 'TITLE_UPDATE') {
          // Dispatch custom event for title updates
          window.dispatchEvent(new CustomEvent('titleUpdate', {
            detail: data
          }))
        }

        // Handle emotion keyword notifications
        if (data.type === 'EMOTION_KEYWORD') {
          // Dispatch custom event for keyword handling (Live2D animations)
          window.dispatchEvent(new CustomEvent('emotionKeyword', {
            detail: data
          }))
        }

        // Handle bash confirmation requests
        if (data.type === 'BASH_CONFIRMATION_REQUEST') {
          // Store in ref for late-mounting components
          pendingConfirmationRef.current = data

          // Dispatch custom event for bash confirmation dialog
          window.dispatchEvent(new CustomEvent('bashConfirmationRequest', {
            detail: data
          }))
        }

        // Handle background process notifications
        if (data.type === 'BACKGROUND_PROCESS_STARTED' ||
            data.type === 'BACKGROUND_PROCESS_OUTPUT_UPDATE' ||
            data.type === 'BACKGROUND_PROCESS_COMPLETED' ||
            data.type === 'BACKGROUND_PROCESS_KILLED') {
          console.log('[ConnectionContext] Dispatching backgroundProcessNotification event:', data)
          // Dispatch custom event for background process monitoring
          window.dispatchEvent(new CustomEvent('backgroundProcessNotification', {
            detail: data
          }))
        }

        // Handle message saved notifications (for tool messages auto-refresh)
        if (data.type === 'MESSAGE_SAVED') {
          console.log('[ConnectionContext] Dispatching messageSaved event:', data)
          // Dispatch custom event to trigger message list refresh
          window.dispatchEvent(new CustomEvent('messageSaved', {
            detail: data
          }))
        }
      } catch (error) {
        console.error("[WebSocket] failed to parse message:", error)
      }
    }
  }, [handleLocationRequest])

  // Disconnect WebSocket connection
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
    setConnectionStatus(() => ConnectionStatus.DISCONNECTED)
  }, [])


  // Send WebSocket message
  const sendWebSocketMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected, cannot send message')
    }
  }, [])

  // Wait for WebSocket connection to establish
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

  // Register location request handler
  const onLocationRequest = useCallback((handler: (data: any) => void) => {
    locationRequestHandler.current = handler
  }, [])

  // Expose pending confirmation ref for late-mounting components
  useEffect(() => {
    // Expose getter and setter functions for pending confirmation
    (window as any).__getPendingConfirmation = () => pendingConfirmationRef.current
    (window as any).__clearPendingConfirmation = () => { pendingConfirmationRef.current = null }
    // Note: No cleanup - these functions should persist for the app lifetime
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

  // Clean up WebSocket connections
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