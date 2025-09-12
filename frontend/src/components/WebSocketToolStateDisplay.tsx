import React from 'react'
import ToolStateDisplay from './Message/tools/ToolStateDisplay'
import { useWebSocketToolStateSimple } from '../hooks/useWebSocketToolState'

/**
 * WebSocket Tool State Display Component
 * 
 * This component replaces SSE-based tool state notifications with WebSocket-based
 * real-time tool state updates. It uses the existing ToolStateDisplay component
 * but gets its data from WebSocket events instead of SSE message parsing.
 * 
 * Integration Strategy:
 * 1. Place this component at the chat interface level (alongside message list)
 * 2. WebSocket tool notifications will be displayed in real-time
 * 3. Remove SSE tool state logic from message parsing
 * 4. Unified WebSocket architecture for all real-time updates
 */
const WebSocketToolStateDisplay: React.FC = () => {
  const toolState = useWebSocketToolStateSimple()

  // Only render when there's an active tool state from WebSocket
  if (!toolState) {
    return null
  }

  return <ToolStateDisplay toolState={toolState} />
}

export default WebSocketToolStateDisplay