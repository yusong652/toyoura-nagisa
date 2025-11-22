/**
 * MessageList - Display chat messages
 */

import React from 'react'
import { Box, Text } from 'ink'
import type { Message, ContentBlock } from '@aiNagisa/core'

interface MessageListProps {
  messages: Message[]
}

const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const renderContentBlock = (block: ContentBlock, index: number) => {
    switch (block.type) {
      case 'text':
        return (
          <Text key={index}>{block.text || ''}</Text>
        )

      case 'thinking':
        return (
          <Text key={index} dimColor italic>
            💭 {block.thinking || ''}
          </Text>
        )

      case 'tool_use':
        return (
          <Box key={index} flexDirection="column" marginLeft={2}>
            <Text color="yellow">🔧 Using tool: {block.name}</Text>
            {block.input && (
              <Text dimColor>{JSON.stringify(block.input, null, 2)}</Text>
            )}
          </Box>
        )

      case 'tool_result':
        return (
          <Box key={index} flexDirection="column" marginLeft={2}>
            <Text color="green">✓ Tool result</Text>
            {block.content && (
              <Text dimColor>{JSON.stringify(block.content, null, 2)}</Text>
            )}
          </Box>
        )

      default:
        return null
    }
  }

  const renderMessage = (message: Message) => {
    const prefix = message.role === 'user' ? '👤 You' : '🤖 Assistant'
    const color = message.role === 'user' ? 'cyan' : 'green'

    return (
      <Box key={message.id} flexDirection="column" marginY={1}>
        <Text bold color={color}>
          {prefix}
          {message.streaming && ' (typing...)'}
        </Text>
        <Box flexDirection="column" marginLeft={2}>
          {message.content.map((block, index) => renderContentBlock(block, index))}
        </Box>
      </Box>
    )
  }

  return (
    <Box flexDirection="column" paddingY={1}>
      {messages.length === 0 ? (
        <Text dimColor>No messages yet. Start chatting!</Text>
      ) : (
        messages.map(renderMessage)
      )}
    </Box>
  )
}

export default MessageList
