import React from 'react'
import DeleteButton from './DeleteButton'
import { MessageActionsProps } from '../types'

/**
 * Message actions container component.
 * 
 * Manages all message interaction controls including delete functionality.
 * Only shows actions when appropriate based on message state.
 * 
 * Args:
 *     messageId: Optional message ID
 *     isSelected: Whether message is currently selected
 *     isLoading: Whether message is currently loading
 *     streaming: Whether message is currently streaming
 *     onDelete: Delete action handler
 * 
 * Returns:
 *     JSX element with action buttons or null if no actions available
 */
const MessageActions: React.FC<MessageActionsProps> = ({
  messageId,
  isSelected,
  isLoading,
  streaming,
  onDelete
}) => {
  const showDelete = isSelected && messageId && !isLoading && !streaming
  
  return (
    <DeleteButton 
      onClick={onDelete}
      visible={showDelete}
    />
  )
}

export default MessageActions