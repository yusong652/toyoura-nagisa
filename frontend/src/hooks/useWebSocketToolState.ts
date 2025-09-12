import { useState, useEffect } from 'react'
import { MessageToolState } from '../types/chat'

interface WebSocketToolData {
  type: string
  tool_names?: string[]
  tool_name?: string
  action?: string
  thinking?: string
  results?: any
  timestamp?: string
}

interface WebSocketToolStateReturn {
  toolState: MessageToolState | null
  sessionId: string | null
  isActive: boolean
}

/**
 * Hook for managing tool state from WebSocket notifications.
 * 
 * This hook listens to WebSocket tool use events and converts them
 * to the MessageToolState format expected by ToolStateDisplay component.
 * 
 * Returns:
 *   WebSocketToolStateReturn: Object containing tool state, session ID, and active status
 */
export const useWebSocketToolState = (): WebSocketToolStateReturn => {
  const [toolState, setToolState] = useState<MessageToolState | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isActive, setIsActive] = useState<boolean>(false)

  useEffect(() => {
    const handleToolStarted = (event: CustomEvent) => {
      const data = event.detail as WebSocketToolData
      
      // Convert WebSocket data to MessageToolState format
      const newToolState: MessageToolState = {
        isUsingTool: true,
        toolNames: data.tool_names || (data.tool_name ? [data.tool_name] : undefined),
        action: data.action,
        thinking: data.thinking
      }
      
      setToolState(newToolState)
      setSessionId(data.session_id || null)
      setIsActive(true)
      console.log('[useWebSocketToolState] Tool started:', newToolState)
    }

    const handleToolConcluded = (event: CustomEvent) => {
      const data = event.detail as WebSocketToolData
      console.log('[useWebSocketToolState] Tool concluded:', data)
      
      setIsActive(false)
      // Keep tool state visible briefly before clearing
      setTimeout(() => {
        setToolState(null)
        setSessionId(null)
      }, 1500) // Show completion state for 1.5 seconds
    }

    // Listen to custom events from ConnectionContext
    window.addEventListener('toolUseStarted', handleToolStarted as EventListener)
    window.addEventListener('toolUseConcluded', handleToolConcluded as EventListener)

    return () => {
      window.removeEventListener('toolUseStarted', handleToolStarted as EventListener)
      window.removeEventListener('toolUseConcluded', handleToolConcluded as EventListener)
    }
  }, [])

  return {
    toolState,
    sessionId,
    isActive
  }
}

// Simplified hook for backward compatibility that only returns the tool state
export const useWebSocketToolStateSimple = (): MessageToolState | null => {
  const { toolState } = useWebSocketToolState()
  return toolState
}

export default useWebSocketToolState