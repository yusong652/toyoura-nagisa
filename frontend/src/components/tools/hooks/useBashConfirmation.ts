import { useState, useEffect, useCallback, useRef } from 'react'

export interface BashConfirmationRequest {
  id: string  // Frontend generated ID for local tracking
  confirmationId: string  // Backend confirmation ID for response
  command: string
  description?: string
  sessionId: string
  timestamp: string
}

interface BashConfirmationState {
  currentRequest: BashConfirmationRequest | null
  isOpen: boolean
}

/**
 * Hook for managing bash command confirmation requests from WebSocket.
 *
 * This hook listens to WebSocket bash confirmation request events and manages
 * the current confirmation dialog. Since backend executes tools serially,
 * only one confirmation request is active at a time.
 *
 * Features:
 * - Single confirmation dialog management
 * - Auto-reject on timeout (60 seconds)
 * - WebSocket message handling for approval/rejection
 *
 * Returns:
 * - currentRequest: Currently displayed bash confirmation request
 * - isOpen: Whether confirmation dialog should be shown
 * - approve: Function to approve current command with optional message
 * - reject: Function to reject current command with optional message
 */
export const useBashConfirmation = () => {
  const [state, setState] = useState<BashConfirmationState>({
    currentRequest: null,
    isOpen: false
  })

  // Debug: Log all state changes
  useEffect(() => {
    console.log('[BashConfirmation Hook] State changed:', {
      currentRequest: state.currentRequest?.command,
      isOpen: state.isOpen,
      timestamp: new Date().toISOString()
    })
  }, [state])

  // Auto-reject timeout reference
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Send response via WebSocket - using global connection like location response
  const sendResponse = useCallback(async (confirmationId: string, approved: boolean, userMessage?: string) => {

    // Try to get WebSocket connection with retry logic
    let ws = (window as any).__wsConnection

    // If not immediately available, try to wait
    if (!ws || ws.readyState !== WebSocket.OPEN) {

      const waitForConnection = (window as any).__waitForConnection
      if (waitForConnection) {
        const connected = await waitForConnection(3000) // Wait up to 3 seconds
        if (connected) {
          ws = (window as any).__wsConnection
        } else {
          console.error('[BashConfirmation] Failed to get WebSocket connection after waiting')
          return
        }
      } else {
        console.error('[BashConfirmation] No waitForConnection available')
        return
      }
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      const response = {
        type: 'BASH_CONFIRMATION_RESPONSE',
        confirmation_id: confirmationId,  // Use actual confirmation ID from backend
        approved,
        user_message: userMessage,
        timestamp: new Date().toISOString()
      }

      const jsonMessage = JSON.stringify(response)

      try {
        ws.send(jsonMessage)
      } catch (error) {
        console.error('[BashConfirmation] Error sending message:', error)
        console.error('[BashConfirmation] WebSocket state at error:', ws.readyState)
      }
    } else {
      console.error('[BashConfirmation] WebSocket still not available after waiting')
    }
  }, [])

  // Clear current request
  const clearCurrentRequest = useCallback(() => {
    setState({
      currentRequest: null,
      isOpen: false
    })
  }, [])

  // Approve command execution - 无状态设计，使用refs获取最新值
  const approve = useCallback(async (userMessage?: string) => {


    if (stateRef.current.currentRequest) {
      const request = stateRef.current.currentRequest

      await sendResponseRef.current(request.confirmationId, true, userMessage)

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }

      // Clear current request
      clearCurrentRequestRef.current()

    } else {
      console.warn('[BashConfirmation] Approve called but no current request found')
    }
  }, []) // 空依赖数组，真正无状态

  // Reject command execution - 无状态设计，使用refs获取最新值
  const reject = useCallback(async (userMessage?: string) => {

    if (stateRef.current.currentRequest) {
      const request = stateRef.current.currentRequest

      await sendResponseRef.current(request.confirmationId, false, userMessage)

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }

      // Dispatch event to clear tool state immediately on rejection
      window.dispatchEvent(new CustomEvent('toolUseConcluded', {
        detail: {
          session_id: request.sessionId,
          reason: 'user_rejection',
          timestamp: new Date().toISOString()
        }
      }))

      // Clear current request
      clearCurrentRequestRef.current()

    } else {
      console.warn('[BashConfirmation] Reject called but no current request found')
    }
  }, []) // 空依赖数组，真正无状态

  // 使用useRef来存储当前的状态和函数，避免依赖问题
  const stateRef = useRef(state)
  stateRef.current = state

  const sendResponseRef = useRef(sendResponse)
  sendResponseRef.current = sendResponse

  const clearCurrentRequestRef = useRef(clearCurrentRequest)
  clearCurrentRequestRef.current = clearCurrentRequest

  useEffect(() => {

    const handleBashConfirmationRequest = (event: CustomEvent) => {
      const data = event.detail

      // Generate unique ID for this request
      const requestId = `bash_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`

      // Parse request
      const request: BashConfirmationRequest = {
        id: requestId,  // Frontend generated ID for local tracking
        confirmationId: data.confirmation_id,  // Backend confirmation ID
        command: data.command,
        description: data.description,
        sessionId: data.session_id || data.sessionId, // Handle both forms
        timestamp: data.timestamp || new Date().toISOString()
      }

      setState(prevState => {
        // Since backend executes serially, we should never have overlapping requests
        // But if we do, log a warning and replace the current request
        if (prevState.currentRequest) {
          console.warn('[BashConfirmation] Received new request while another is active (unexpected with serial execution)')
        }
        return {
          currentRequest: request,
          isOpen: true
        }
      })

    }

    // Listen to custom event from ConnectionContext
    window.addEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)

    return () => {
      window.removeEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)

      // Clean up timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, []) // 空依赖数组，只在mount/unmount时执行

  // Set up timeout for current request
  useEffect(() => {
    if (state.currentRequest && state.isOpen) {

      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        const currentRequest = stateRef.current.currentRequest
        if (currentRequest) {
          // Use the current sendResponse function from ref
          sendResponseRef.current(currentRequest.confirmationId, false, 'Command confirmation timed out').then(() => {
            // Dispatch event to clear tool state on timeout rejection
            window.dispatchEvent(new CustomEvent('toolUseConcluded', {
              detail: {
                session_id: currentRequest.sessionId,
                reason: 'user_rejection',
                timestamp: new Date().toISOString()
              }
            }))

            // Clear current request
            clearCurrentRequestRef.current()
          })
        }
      }, 60000)
    }
  }, [state.currentRequest, state.isOpen])

  return {
    currentRequest: state.currentRequest,
    isOpen: state.isOpen,
    approve,
    reject
  }
}

export default useBashConfirmation