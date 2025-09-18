import { useState, useEffect, useCallback, useRef } from 'react'

export interface BashConfirmationRequest {
  confirmationId: string
  command: string
  description?: string
  sessionId?: string
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
        confirmation_id: confirmationId,
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

  // Approve command execution
  const approve = useCallback(async (userMessage?: string) => {
    if (state.request) {
      await sendResponse(state.request.confirmationId, true, userMessage)
      setState({ request: null, isOpen: false })

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [state.request, sendResponse])

  // Reject command execution
  const reject = useCallback(async (userMessage?: string) => {
    if (state.request) {
      await sendResponse(state.request.confirmationId, false, userMessage)
      setState({ request: null, isOpen: false })

      // Clear timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [state.request, sendResponse])

  useEffect(() => {
    const handleBashConfirmationRequest = (event: CustomEvent) => {
      const data = event.detail

      // Parse request
      const request: BashConfirmationRequest = {
        confirmationId: data.confirmation_id,
        command: data.command,
        description: data.description,
        sessionId: data.session_id || data.sessionId, // Handle both forms
        timestamp: data.timestamp || new Date().toISOString()
      }

      setState({ request, isOpen: true })
      console.log('[BashConfirmation] Received request:', request)

      // Set auto-reject timeout (60 seconds)
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        console.log('[BashConfirmation] Auto-rejecting due to timeout')
        reject('Command confirmation timed out')
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
  }, [reject])

  return {
    request: state.request,
    isOpen: state.isOpen,
    approve,
    reject
  }
}

export default useBashConfirmation