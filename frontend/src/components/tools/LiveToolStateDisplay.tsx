import React, { useEffect, useRef } from 'react'
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
 * - Automatic scrolling to keep tool state visible
 * - Zero configuration required
 *
 * Note:
 * Bash confirmation logic has been migrated to ToolUseBlock component
 * for better context integration and message history visibility.
 *
 * Usage:
 * Place this component at the chat interface level to show real-time
 * tool usage feedback to users.
 */
const LiveToolStateDisplay: React.FC = () => {
  const toolState = useWebSocketToolStateSimple()
  const displayRef = useRef<HTMLDivElement>(null)

  // Auto-scroll when tool state changes
  useEffect(() => {
    if (toolState && displayRef.current) {
      // Find the closest scrollable parent (ChatBox)
      let scrollableParent = displayRef.current.parentElement
      while (scrollableParent) {
        const style = window.getComputedStyle(scrollableParent)
        if (style.overflowY === 'auto' || style.overflowY === 'scroll' ||
            scrollableParent.classList.contains('chatbox')) {
          break
        }
        scrollableParent = scrollableParent.parentElement
      }

      if (scrollableParent) {
        // Delay scroll to ensure the component has rendered
        setTimeout(() => {
          const scrollPosition = scrollableParent.scrollHeight - scrollableParent.clientHeight * 0.8
          scrollableParent.scrollTo({
            top: scrollPosition,
            behavior: 'smooth'
          })
        }, 100)
      }
    }
  }, [toolState?.action, toolState?.thinking, toolState?.isUsingTool, toolState?.toolNames])

  return (
    <>
      {/* Only render ToolStateDisplay when there's an active tool state from WebSocket */}
      {toolState && (
        <div ref={displayRef}>
          <ToolStateDisplay toolState={toolState} />
        </div>
      )}
    </>
  )
}

export default LiveToolStateDisplay