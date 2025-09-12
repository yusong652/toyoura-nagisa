import { MessageToolState } from '../../types/chat'

/**
 * Tool state display component properties.
 * 
 * Defines the interface for components that display tool usage information
 * including tool names, action text, and thinking content.
 */
export interface ToolStateDisplayProps {
  toolState: MessageToolState
}