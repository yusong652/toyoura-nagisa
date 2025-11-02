import React from 'react'
import { MessageAvatarProps } from '../types'

/**
 * Message avatar display component.
 *
 * Displays appropriate avatar image based on message role with hover tooltip support.
 * Handles avatar loading and positioning for both user and assistant messages.
 *
 * Args:
 *     role: Message role type (MessageRole)
 *     onMouseEnter: Optional mouse enter handler for tooltip display
 *     onMouseLeave: Optional mouse leave handler for tooltip cleanup
 *
 * Returns:
 *     JSX element with avatar image and event handlers
 */
const MessageAvatar: React.FC<MessageAvatarProps> = ({
  role,
  onMouseEnter,
  onMouseLeave
}) => {
  const avatarSrc = role === 'user' ? '/user-avatar.jpg' : '/Nagisa_avatar.png'
  const altText = role === 'user' ? 'User' : 'Nagisa'
  
  return (
    <img 
      src={avatarSrc}
      alt={altText}
      className="avatar"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    />
  )
}

export default MessageAvatar