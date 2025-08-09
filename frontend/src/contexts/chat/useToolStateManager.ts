import { useCallback } from 'react'

interface UseToolStateManagerProps {
  setToolState: (state: any) => void
  updateMessageToolState: (messageId: string, toolState: any) => void
}

interface ToolStateManager {
  handleToolStart: (messageId: string, data: any) => void
  handleToolEnd: (messageId: string, data: any) => void
}

/**
 * Hook for managing tool usage state during stream processing.
 * 
 * Tracks when tools are being used and updates both global and message-specific tool states.
 * Extracted from useStreamHandler for better modularity.
 */
export const useToolStateManager = ({
  setToolState,
  updateMessageToolState
}: UseToolStateManagerProps): ToolStateManager => {

  /**
   * Handle tool usage start event.
   * 
   * Updates both global tool state and message-specific tool state.
   */
  const handleToolStart = useCallback((messageId: string, data: any) => {
    const toolState = {
      isUsingTool: true,
      toolName: data.tool_name,
      action: data.action_text
    }
    
    // Update message-specific tool state
    updateMessageToolState(messageId, toolState)
    
    // Update global tool state
    setToolState(data)
  }, [updateMessageToolState, setToolState])

  /**
   * Handle tool usage end event.
   * 
   * Clears tool usage state when tool execution completes.
   */
  const handleToolEnd = useCallback((messageId: string, data: any) => {
    const toolState = {
      isUsingTool: false
    }
    
    // Update message-specific tool state
    updateMessageToolState(messageId, toolState)
    
    // Update global tool state
    setToolState(data)
  }, [updateMessageToolState, setToolState])

  return {
    handleToolStart,
    handleToolEnd
  }
}