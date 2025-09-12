import React from 'react'
import ToolStateDisplay from './ToolStateDisplay'
import { useWebSocketToolStateSimple } from '../../hooks/useWebSocketToolState'

/**
 * Live Tool State Display Component
 * 
 * A WebSocket-powered real-time tool state display that shows active tool usage
 * information as it happens. This component combines the base ToolStateDisplay
 * with WebSocket event handling for live updates.
 * 
 * Features:
 * - Real-time WebSocket tool state updates
 * - Automatic show/hide based on tool activity
 * - Consistent UI with existing tool state displays
 * - Zero configuration required
 * 
 * Usage:
 * Place this component at the chat interface level to show real-time
 * tool usage feedback to users.
 */
const LiveToolStateDisplay: React.FC = () => {
  const toolState = useWebSocketToolStateSimple()

  // Only render when there's an active tool state from WebSocket
  if (!toolState) {
    return null
  }

  return <ToolStateDisplay toolState={toolState} />
}

export default LiveToolStateDisplay