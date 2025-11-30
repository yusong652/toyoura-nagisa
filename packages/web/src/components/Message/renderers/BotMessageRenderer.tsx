import React from 'react'
import StreamingTextRenderer from './StreamingTextRenderer'
import MessageFiles from '../content/MessageFiles'
import MessageTimestamp from '../content/MessageTimestamp'
import ToolUseBlock from '../content/ToolUseBlock'
import ToolDiffBlock from '../content/ToolDiffBlock'
import ThinkingBlock from '../content/ThinkingBlock'
import { BotMessageRendererProps } from '../types'
import { ContentBlock } from '@toyoura-nagisa/core'

/**
 * Bot message renderer component.
 *
 * Renders complex bot messages with content blocks (text, tool_use, thinking),
 * file attachments, and timestamp. Handles both streaming and static content.
 * Supports structured multimodal content with tool calls.
 *
 * Args:
 *     message: Message object with bot content and tool state
 *     isSelected: Whether message is currently selected
 *     onMessageClick: Message click handler for selection
 *     onImageClick: Image click handler for viewer
 *     onVideoClick: Video click handler for player
 *
 * Returns:
 *     JSX element with rendered bot message content
 */
const BotMessageRenderer: React.FC<BotMessageRendererProps> = ({
  message,
  onImageClick,
  onVideoClick
}) => {
  const { files, isLoading, streaming, text, content } = message

  // Render content blocks if available, otherwise fall back to text
  const renderContentBlocks = () => {
    if (!content || content.length === 0) {
      // Legacy text-only message
      const displayText = text || ''
      const chunks: string[] = []

      // Show streaming indicator even if text is empty (e.g., tool calls without text)
      if (displayText.trim() === '' && (streaming || isLoading)) {
        return (
          <StreamingTextRenderer
            displayText=""
            chunks={chunks}
            streaming={streaming || false}
            isLoading={isLoading || false}
          />
        )
      }

      if (displayText.trim() === '') return null

      return (
        <StreamingTextRenderer
          displayText={displayText}
          chunks={chunks}
          streaming={streaming || false}
          isLoading={isLoading || false}
        />
      )
    }

    // Render structured content blocks
    const blocks = content.map((block, index) => {
      switch (block.type) {
        case 'text':
          // Always render text blocks during streaming, even if empty
          // This ensures message is visible while waiting for tool calls
          if (!block.text && !streaming && !isLoading) {
            return null
          }
          return (
            <StreamingTextRenderer
              key={index}
              displayText={block.text || ''}
              chunks={[]}
              streaming={streaming || false}
              isLoading={isLoading || false}
            />
          )
        case 'tool_use':
          // Route to specialized component based on tool type
          if (block.name === 'edit' || block.name === 'write') {
            return <ToolDiffBlock key={index} block={block} messageId={message.id} />
          }
          return <ToolUseBlock key={index} block={block} messageId={message.id} />
        case 'thinking':
          return <ThinkingBlock key={index} block={block} streaming={streaming} />
        default:
          return null
      }
    })

    // Filter out null blocks
    const validBlocks = blocks.filter(block => block !== null)

    // If no valid blocks and streaming, show at least a placeholder
    if (validBlocks.length === 0 && (streaming || isLoading)) {
      return (
        <StreamingTextRenderer
          displayText=""
          chunks={[]}
          streaming={streaming || false}
          isLoading={isLoading || false}
        />
      )
    }

    return validBlocks
  }

  const hasFiles = files && files.length > 0 && !isLoading

  return (
    <div className="message-wrapper">
      <div className="message-content">
        {/* Render content blocks or legacy text */}
        {renderContentBlocks()}

        {/* Render file attachments */}
        {hasFiles && (
          <MessageFiles
            files={files}
            isLoading={isLoading || false}
            onImageClick={onImageClick}
            onVideoClick={onVideoClick}
            role="assistant"
          />
        )}

        <MessageTimestamp timestamp={message.timestamp} />
      </div>
    </div>
  )
}

export default BotMessageRenderer