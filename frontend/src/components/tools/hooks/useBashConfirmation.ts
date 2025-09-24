import { useState, useEffect, useCallback, useRef } from 'react'

export interface BashConfirmationRequest {
  command: string
  description?: string
  sessionId: string
  timestamp: string
}

interface BashConfirmationState {
  request: BashConfirmationRequest | null
  isOpen: boolean
}

/**
 * Hook for managing bash command confirmation requests from WebSocket.
 *
 * This hook listens to WebSocket bash confirmation request events and provides
 * methods to approve or reject the command execution.
 *
 * Features:
 * - Listens to BASH_CONFIRMATION_REQUEST WebSocket messages
 * - Provides approve/reject methods
 * - Sends BASH_CONFIRMATION_RESPONSE back via WebSocket
 * - Auto-reject on timeout (60 seconds)
 *
 * Returns:
 * - request: Current bash confirmation request
 * - isOpen: Whether confirmation dialog should be shown
 * - approve: Function to approve command with optional message
 * - reject: Function to reject command with optional message
 */
export const useBashConfirmation = () => {
  const [state, setState] = useState<BashConfirmationState>({
    request: null,
    isOpen: false
  })

  // Debug: Log all state changes
  useEffect(() => {
    console.log('[BashConfirmation Hook] State changed:', {
      request: state.request?.command,
      isOpen: state.isOpen,
      timestamp: new Date().toISOString()
    })
  }, [state])

  // Auto-reject timeout reference
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Send response via WebSocket - using global connection like location response
  const sendResponse = useCallback(async (sessionId: string, approved: boolean, userMessage?: string) => {

    // Try to get WebSocket connection with retry logic
    let ws = (window as any).__wsConnection

    // If not immediately available, try to wait
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.log('[BashConfirmation] WebSocket not ready, waiting for connection...')

      const waitForConnection = (window as any).__waitForConnection
      if (waitForConnection) {
        const connected = await waitForConnection(3000) // Wait up to 3 seconds
        if (connected) {
          ws = (window as any).__wsConnection
          console.log('[BashConfirmation] Got connection after waiting')
        } else {
          console.error('[BashConfirmation] Failed to get WebSocket connection after waiting')
          return
        }
      } else {
        console.error('[BashConfirmation] No waitForConnection available')
        return
      }
    }

    console.log('[BashConfirmation] Using WebSocket:', ws)
    console.log('[BashConfirmation] WebSocket readyState:', ws?.readyState)

    if (ws && ws.readyState === WebSocket.OPEN) {
      const response = {
        type: 'BASH_CONFIRMATION_RESPONSE',
        confirmation_id: sessionId,  // Backend expects confirmation_id field but uses session_id value
        approved,
        user_message: userMessage,
        timestamp: new Date().toISOString()
      }

      const jsonMessage = JSON.stringify(response)
      console.log('[BashConfirmation] Sending response:', response)

      try {
        ws.send(jsonMessage)
        console.log('[BashConfirmation] Successfully sent response')
      } catch (error) {
        console.error('[BashConfirmation] Error sending message:', error)
        console.error('[BashConfirmation] WebSocket state at error:', ws.readyState)
      }
    } else {
      console.error('[BashConfirmation] WebSocket still not available after waiting')
    }
  }, [])

  // Approve command execution - 无状态设计，使用refs获取最新值
  const approve = useCallback(async (userMessage?: string) => {
    console.log('[BashConfirmation] Approve called:', {
      currentState: stateRef.current,
      userMessage
    })

    if (stateRef.current.request) {
      const sessionId = stateRef.current.request.sessionId
      console.log('[BashConfirmation] Sending approval for session:', sessionId)

      await sendResponseRef.current(sessionId, true, userMessage)
      setState({ request: null, isOpen: false })

      console.log('[BashConfirmation] State cleared after approval')

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    } else {
      console.warn('[BashConfirmation] Approve called but no request found')
    }
  }, []) // 空依赖数组，真正无状态

  // Reject command execution - 无状态设计，使用refs获取最新值
  const reject = useCallback(async (userMessage?: string) => {
    console.log('[BashConfirmation] Reject called:', {
      currentState: stateRef.current,
      userMessage
    })

    if (stateRef.current.request) {
      const sessionId = stateRef.current.request.sessionId
      console.log('[BashConfirmation] Sending rejection for session:', sessionId)

      await sendResponseRef.current(sessionId, false, userMessage)
      setState({ request: null, isOpen: false })

      console.log('[BashConfirmation] State cleared after rejection')

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }

      // Dispatch event to clear tool state immediately on rejection
      window.dispatchEvent(new CustomEvent('toolUseConcluded', {
        detail: {
          session_id: sessionId,
          reason: 'user_rejection',
          timestamp: new Date().toISOString()
        }
      }))
      console.log('[BashConfirmation] Dispatched toolUseConcluded event after rejection')
    } else {
      console.warn('[BashConfirmation] Reject called but no request found')
    }
  }, []) // 空依赖数组，真正无状态

  // 使用useRef来存储当前的状态和函数，避免依赖问题
  const stateRef = useRef(state)
  stateRef.current = state

  const sendResponseRef = useRef(sendResponse)
  sendResponseRef.current = sendResponse

  useEffect(() => {
    console.log('[BashConfirmation] Setting up event listener for bashConfirmationRequest (mount only)')

    const handleBashConfirmationRequest = (event: CustomEvent) => {
      console.log('[BashConfirmation] Event received:', event)
      const data = event.detail
      console.log('[BashConfirmation] Event detail data:', data)

      // Parse request
      const request: BashConfirmationRequest = {
        command: data.command,
        description: data.description,
        sessionId: data.session_id || data.sessionId, // Handle both forms
        timestamp: data.timestamp || new Date().toISOString()
      }

      console.log('[BashConfirmation] Parsed request:', request)
      setState({ request, isOpen: true })
      console.log('[BashConfirmation] State updated with request')

      // Set auto-reject timeout (60 seconds)
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        console.log('[BashConfirmation] Auto-rejecting due to timeout')
        // Use the current sendResponse function from ref
        sendResponseRef.current(request.sessionId, false, 'Command confirmation timed out').then(() => {
          setState({ request: null, isOpen: false })

          // Dispatch event to clear tool state on timeout rejection
          window.dispatchEvent(new CustomEvent('toolUseConcluded', {
            detail: {
              session_id: request.sessionId,
              reason: 'user_rejection',
              timestamp: new Date().toISOString()
            }
          }))
          console.log('[BashConfirmation] Dispatched toolUseConcluded event after timeout rejection')
        })
      }, 60000)
    }

    // Listen to custom event from ConnectionContext
    window.addEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)

    return () => {
      window.removeEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)

      // Clean up timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, []) // 空依赖数组，只在mount/unmount时执行

  return {
    request: state.request,
    isOpen: state.isOpen,
    approve,
    reject
  }
}

export default useBashConfirmation