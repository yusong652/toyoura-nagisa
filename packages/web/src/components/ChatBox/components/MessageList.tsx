/**
 * Message list component for rendering chat messages.
 * 
 * This component demonstrates:
 * - Array mapping with TypeScript
 * - Component composition
 * - Props passing patterns
 * - Key prop usage in lists
 */

import React from 'react'
import { MessageItem } from '../../Message'
import { MessageListProps } from '../types'

/**
 * Renders a list of chat messages with selection handling.
 * 
 * This component is responsible for:
 * - Mapping over message array
 * - Passing selection state to each message
 * - Providing message context (all messages for navigation)
 * 
 * Args:
 *     messages: Array of messages to render
 *     selectedMessageId: Currently selected message ID
 *     onMessageSelect: Selection handler callback
 * 
 * TypeScript Learning Points:
 * - Array.map with type inference
 * - Component prop spreading vs explicit passing
 * - Key prop requirements in React lists
 */
const MessageList: React.FC<MessageListProps> = ({
  messages,
  selectedMessageId,
  onMessageSelect
}) => {
  return (
    <>
      {messages.map((message) => (
        <MessageItem 
          key={message.id}                    // React key for list rendering
          message={message}                   // Message data
          selectedMessageId={selectedMessageId} // Selection state
          onMessageSelect={onMessageSelect}   // Selection handler
          allMessages={messages}              // Context for image navigation
        />
      ))}
    </>
  )
}

export default MessageList

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Array Mapping:
 *    messages.map((message) => ...) - TypeScript infers message type
 * 
 * 2. Component Props:
 *    Each prop is type-checked against MessageItem's interface
 * 
 * 3. Fragment Shorthand:
 *    <> ... </> - React.Fragment without explicit import
 * 
 * 4. Key Prop:
 *    key={message.id} - Required for React list optimization
 * 
 * 5. Prop Passing Patterns:
 *    Could use spread: {...message} vs explicit: message={message}
 *    Explicit is clearer for TypeScript and maintainability
 * 
 * Why separate this component?
 * - Single responsibility: only handles list rendering
 * - Reusable if we need message lists elsewhere
 * - Easier to test in isolation
 * - Performance: can be memoized if needed
 */