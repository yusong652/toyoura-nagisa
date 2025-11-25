import React from 'react'
import { formatSmartTime } from '@aiNagisa/core/utils'
import { MessageTimestampProps } from '../types'

/**
 * Message timestamp display component.
 * 
 * Formats and displays message timestamps with smart relative time display.
 * Shows relative time (e.g., "2 minutes ago") with full timestamp on hover.
 * 
 * Args:
 *     timestamp: Unix timestamp in milliseconds
 *     className: Optional CSS class name (defaults to 'message-time')
 * 
 * Returns:
 *     JSX element with formatted timestamp display
 */
const MessageTimestamp: React.FC<MessageTimestampProps> = ({ 
  timestamp, 
  className = 'message-time' 
}) => {
  const timeData = formatSmartTime(timestamp, { showRelative: true })
  
  return (
    <span className={className} title={timeData.fullTime}>
      {timeData.display}
    </span>
  )
}

export default MessageTimestamp