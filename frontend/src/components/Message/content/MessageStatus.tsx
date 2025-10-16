import React from 'react'
import { MessageStatus } from '../../../types/chat'
import { MessageStatusProps } from '../types'

/**
 * Message status indicator component.
 *
 * Displays message delivery status for user messages with appropriate styling.
 * Only renders for user messages as assistant messages don't need status indicators.
 *
 * Args:
 *     status: Message status enum (SENDING, SENT, READ, ERROR)
 *     role: Message role type (MessageRole)
 *
 * Returns:
 *     JSX element with status indicator or null for assistant messages
 */
const MessageStatusComponent: React.FC<MessageStatusProps> = ({ status, role }) => {
  // Only show status for user messages
  if (role !== 'user') return null
  
  let statusText = ''
  let statusClass = ''
  
  if (status === MessageStatus.SENDING) {
    statusText = 'Sending'
    statusClass = 'status-sending'
  } else if (status === MessageStatus.SENT) {
    statusText = 'Sent'
    statusClass = 'status-sent'
  } else if (status === MessageStatus.READ) {
    statusText = 'Read'
    statusClass = 'status-read'
  } else if (status === MessageStatus.ERROR) {
    statusText = 'Failed'
    statusClass = 'status-error'
  } else {
    // No status info messages (like history messages) default to read
    statusText = 'Read'
    statusClass = 'status-read'
  }
  
  return (
    <div className={`message-status ${statusClass}`}>
      {statusText}
    </div>
  )
}

export default MessageStatusComponent