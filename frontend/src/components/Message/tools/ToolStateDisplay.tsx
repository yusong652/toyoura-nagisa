import React from 'react'
import MessageToolState from '../../MessageToolState'
import { ToolStateDisplayProps } from '../types'

/**
 * Tool state display wrapper component.
 * 
 * Simple wrapper around existing MessageToolState component to maintain
 * consistency with the new architecture while reusing existing logic.
 * 
 * Args:
 *     toolState: Tool state object with usage information
 * 
 * Returns:
 *     JSX element with tool state display or null if no tool state
 */
const ToolStateDisplay: React.FC<ToolStateDisplayProps> = ({ toolState }) => {
  if (!toolState) return null
  
  return <MessageToolState toolState={toolState} />
}

export default ToolStateDisplay