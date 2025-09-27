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
  queue: BashConfirmationRequest[]
  currentRequest: BashConfirmationRequest | null
  isOpen: boolean
}

/**
 * Hook for managing bash command confirmation requests queue from WebSocket.
 *
 * This hook listens to WebSocket bash confirmation request events and manages
 * a queue of pending requests, showing one confirmation dialog at a time.
 *
 * Features:
 * - Queue-based management of multiple bash confirmation requests
 * - One-at-a-time confirmation dialog display
 * - Auto-processing of queue after each confirmation
 * - Auto-reject on timeout (60 seconds) for current request
 * - Unique ID generation for each bash command
 *
 * Returns:
 * - currentRequest: Currently displayed bash confirmation request
 * - queueLength: Number of pending requests in queue
 * - isOpen: Whether confirmation dialog should be shown
 * - approve: Function to approve current command with optional message
 * - reject: Function to reject current command with optional message
 */
export const useBashConfirmation = () => {
  const [state, setState] = useState<BashConfirmationState>({
    queue: [],
    currentRequest: null,
    isOpen: false
  })

  // Debug: Log all state changes
  useEffect(() => {
    console.log('[BashConfirmation Hook] State changed:', {
      currentRequest: state.currentRequest?.command,
      queueLength: state.queue.length,
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
        confirmation_id: confirmationId,  // Use actual confirmation ID from backend
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

  // Process next request in queue
  const processNextRequest = useCallback(() => {
    setState(prevState => {
      if (prevState.queue.length > 0) {
        const [nextRequest, ...remainingQueue] = prevState.queue
        console.log('[BashConfirmation] Processing next request from queue:', nextRequest.command)
        return {
          queue: remainingQueue,
          currentRequest: nextRequest,
          isOpen: true
        }
      } else {
        return {
          queue: [],
          currentRequest: null,
          isOpen: false
        }
      }
    })
  }, [])

  // Approve command execution - 无状态设计，使用refs获取最新值
  const approve = useCallback(async (userMessage?: string) => {
    console.log('[BashConfirmation] Approve called:', {
      currentState: stateRef.current,
      userMessage
    })

    if (stateRef.current.currentRequest) {
      const request = stateRef.current.currentRequest
      console.log('[BashConfirmation] Sending approval for request:', request.id)

      await sendResponseRef.current(request.confirmationId, true, userMessage)

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }

      // Process next request in queue
      processNextRequestRef.current()

      console.log('[BashConfirmation] Processed approval and moved to next request')
    } else {
      console.warn('[BashConfirmation] Approve called but no current request found')
    }
  }, []) // 空依赖数组，真正无状态

  // Reject command execution - 无状态设计，使用refs获取最新值
  const reject = useCallback(async (userMessage?: string) => {
    console.log('[BashConfirmation] Reject called:', {
      currentState: stateRef.current,
      userMessage
    })

    if (stateRef.current.currentRequest) {
      const request = stateRef.current.currentRequest
      console.log('[BashConfirmation] Sending rejection for request:', request.id)

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
      console.log('[BashConfirmation] Dispatched toolUseConcluded event after rejection')

      // Process next request in queue
      processNextRequestRef.current()

      console.log('[BashConfirmation] Processed rejection and moved to next request')
    } else {
      console.warn('[BashConfirmation] Reject called but no current request found')
    }
  }, []) // 空依赖数组，真正无状态

  // 使用useRef来存储当前的状态和函数，避免依赖问题
  const stateRef = useRef(state)
  stateRef.current = state

  const sendResponseRef = useRef(sendResponse)
  sendResponseRef.current = sendResponse

  const processNextRequestRef = useRef(processNextRequest)
  processNextRequestRef.current = processNextRequest

  useEffect(() => {
    console.log('[BashConfirmation] Setting up event listener for bashConfirmationRequest (mount only)')

    const handleBashConfirmationRequest = (event: CustomEvent) => {
      console.log('[BashConfirmation] Event received:', event)
      const data = event.detail
      console.log('[BashConfirmation] Event detail data:', data)

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

      console.log('[BashConfirmation] Parsed request:', request)

      setState(prevState => {
        // If no current request, set this as current
        if (!prevState.currentRequest) {
          console.log('[BashConfirmation] Setting as current request (no queue)')
          return {
            queue: prevState.queue,
            currentRequest: request,
            isOpen: true
          }
        } else {
          // Add to queue
          console.log('[BashConfirmation] Adding to queue (current request exists)')
          return {
            queue: [...prevState.queue, request],
            currentRequest: prevState.currentRequest,
            isOpen: prevState.isOpen
          }
        }
      })

      console.log('[BashConfirmation] State updated with request')
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
      console.log('[BashConfirmation] Setting timeout for current request:', state.currentRequest.id)

      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        console.log('[BashConfirmation] Auto-rejecting due to timeout:', state.currentRequest?.id)
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
            console.log('[BashConfirmation] Dispatched toolUseConcluded event after timeout rejection')

            // Process next request in queue
            processNextRequestRef.current()
          })
        }
      }, 60000)
    }
  }, [state.currentRequest, state.isOpen])

  return {
    currentRequest: state.currentRequest,
    queueLength: state.queue.length,
    isOpen: state.isOpen,
    approve,
    reject
  }
}

export default useBashConfirmation