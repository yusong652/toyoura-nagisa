import React, { useState, useEffect } from 'react'
import './ToolStateDisplay.css'
import { ToolStateDisplayProps } from './types'
import { MessageToolState as MessageToolStateType } from '../../types/chat'

/**
 * Tool state display component.
 * 
 * Displays tool usage state including tool name and thinking content.
 * Handles scrolling animation for long thinking content and provides
 * visual feedback during tool processing.
 * 
 * Args:
 *     toolState: Tool state object with usage information
 * 
 * Returns:
 *     JSX element with tool state display or null if no tool state
 */
const ToolStateDisplay: React.FC<ToolStateDisplayProps> = ({ toolState }) => {
  // 所有 Hooks 必须在任何条件判断之前调用
  const [displayedText, setDisplayedText] = useState('')
  const [isScrolling, setIsScrolling] = useState(false)
  const [animationDuration, setAnimationDuration] = useState(10)
  const [scrollDistance, setScrollDistance] = useState('-50%')

  // 提前获取必要的值，避免在 useEffect 之前有条件性 return
  const isUsingTool = toolState?.isUsingTool
  const toolNames = toolState?.toolNames
  const thinking = toolState?.thinking
  const thinkingContent = thinking || 'Processing...'
  
  useEffect(() => {
    // 在 useEffect 内部处理条件逻辑
    if (!toolState || !isUsingTool) {
      setDisplayedText('Processing...')
      return
    }
    if (!thinkingContent || thinkingContent === 'Processing...') {
      setDisplayedText('Processing...')
      return
    }

    // Check content length for display decision
    const sentences = thinkingContent.split(/[.!?]+/).filter(s => s.trim().length > 0)
    const words = thinkingContent.split(' ')
    
    // For short content, display it directly without any processing
    if (words.length <= 40 || sentences.length <= 3) { // Increased threshold
      setDisplayedText(thinkingContent)
      setIsScrolling(false)
      return
    }

    // For long content, keep it complete - no artificial line breaking
    // Just display the full content for scrolling
    setDisplayedText(thinkingContent)
    setIsScrolling(true)

    // Calculate scroll distance to show the end of content
    // Estimate content height based on character count and viewport
    const viewportHeight = 120 // Current viewport height in pixels
    const avgCharsPerLine = 50 // Approximate characters per line
    const lineHeight = 16.8 // font-size (12px) * line-height (1.4)
    
    const estimatedLines = Math.ceil(thinkingContent.length / avgCharsPerLine)
    const contentHeight = estimatedLines * lineHeight + 16 // +16 for padding
    
    // Calculate how much to scroll to show the end
    const scrollAmount = Math.max(0, contentHeight - viewportHeight)
    const scrollPercentage = (scrollAmount / contentHeight) * 100
    
    setScrollDistance(`-${Math.min(scrollPercentage, 85)}%`) // Cap at 85% to always show some content
    
    // Calculate animation duration purely based on content length - no minimum
    const totalWords = words.length
    const totalChars = thinkingContent.length
    
    // Dynamic duration based purely on content complexity
    const contentFactor = totalWords * 0.08 // 0.08 seconds per word
    const charFactor = totalChars * 0.015 // 0.015 seconds per character
    
    // Total duration: no minimum, capped at 8 seconds for very long content
    const duration = Math.min(contentFactor + charFactor, 8)
    setAnimationDuration(duration)
  }, [toolState, isUsingTool, thinkingContent])

  // 条件性 return 放在所有 Hooks 之后
  if (!toolState || !isUsingTool) {
    return null
  }

  return (
    <div className="message-tool-state">
      <div className="message-tool-state-content">
        <div className="message-tool-thinking-container">
          <div className="message-tool-thinking-viewport">
            {toolNames && toolNames.length > 0 && (
              <div className="message-tool-name">
                <div className="tool-name-icon"></div>
                <span className="tool-name-text">
                  {toolNames.length === 1 
                    ? toolNames[0] 
                    : `${toolNames.length} tools: ${toolNames.join(', ')}`
                  }
                </span>
              </div>
            )}
            <div 
              className={`message-tool-thinking-content ${isScrolling ? 'scrolling' : ''}`}
              style={{
                animationDuration: `${animationDuration}s`,
                '--scroll-end': scrollDistance
              } as React.CSSProperties}
            >
              {displayedText}
              {/* 始终显示思考动画点，表示模型正在思考中 */}
              <span className="thinking-dots">
                <span className="dot dot-1">•</span>
                <span className="dot dot-2">•</span>
                <span className="dot dot-3">•</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ToolStateDisplay