import React from 'react'

interface DeleteButtonProps {
  onClick: (e: React.MouseEvent) => void
  visible: boolean
}

/**
 * Message delete button component.
 * 
 * Displays a delete button for selected messages with appropriate styling.
 * Only visible when the message is selected and not currently loading.
 * 
 * Args:
 *     onClick: Click handler for delete action
 *     visible: Whether the button should be visible
 * 
 * Returns:
 *     JSX element with delete button or null if not visible
 */
const DeleteButton: React.FC<DeleteButtonProps> = ({ onClick, visible }) => {
  if (!visible) return null
  
  return (
    <div className="message-delete-button" onClick={onClick}>
      <svg width="12" height="12" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path 
          d="M2 2L12 12M2 12L12 2" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

export default DeleteButton