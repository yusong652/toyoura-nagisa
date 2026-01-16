/**
 * TypeScript type definitions for ChatBox module.
 * 
 * This file provides comprehensive type definitions for the ChatBox component
 * and its sub-components, demonstrating TypeScript best practices including
 * interface design, optional properties, and function type signatures.
 */

import { Message } from '@toyoura-nagisa/core'

/**
 * Main ChatBox component props interface.
 * 
 * Currently empty as ChatBox uses contexts directly, but prepared for
 * future prop-based configuration if needed.
 */
export interface ChatBoxProps {
  // Reserved for future configuration props
}

/**
 * ChatBox title bar component props.
 * 
 * Demonstrates optional properties and function signatures for event handlers.
 * The title bar displays session information and provides title refresh functionality.
 */
export interface ChatBoxTitleBarProps {
  currentSessionTitle: string                    // Required: Current session title to display
  currentSessionId: string | null               // Optional: Session ID, null for new sessions
  isRefreshingTitle: boolean                    // Required: Loading state for refresh operation
  canRefreshTitle: boolean                      // Required: Whether refresh is allowed
  onRefreshTitle: () => Promise<void>          // Required: Async handler for title refresh
}

/**
 * Message list component props.
 * 
 * Shows array type usage and callback function signatures.
 * This component renders the scrollable list of chat messages.
 */
export interface MessageListProps {
  messages: Message[]                           // Required: Array of messages to display
  selectedMessageId: string | null             // Optional: Currently selected message
  onMessageSelect: (id: string | null) => void // Required: Selection handler
}

/**
 * ChatBox controls component props.
 * 
 * Placeholder for future control elements.
 */
export interface ChatBoxControlsProps {
  // Empty for now - future controls can be added here
}

/**
 * Scroll behavior hook return type.
 * 
 * Demonstrates hook return type interface pattern for custom hooks.
 * Provides refs and handlers for scroll management.
 */
export interface UseScrollBehaviorReturn {
  chatboxRef: React.RefObject<HTMLDivElement>   // Ref to chatbox container
  handleChatboxClick: (e: React.MouseEvent) => void // Click handler for selection
}

/**
 * Title management hook return type.
 * 
 * Shows how to type complex hook returns with state and handlers.
 */
export interface UseTitleManagementReturn {
  currentSessionTitle: string                   // Computed session title
  currentSessionId: string | null              // Current session ID
  isRefreshingTitle: boolean                    // Loading state
  canRefreshTitle: boolean                      // Computed refresh permission
  handleRefreshTitle: () => Promise<void>      // Async refresh handler
}

/**
 * Message selection hook return type.
 * 
 * Simple state management hook interface.
 */
export interface UseMessageSelectionReturn {
  selectedMessageId: string | null             // Current selection
  setSelectedMessageId: (id: string | null) => void // Selection setter
}

/**
 * Refresh button props for icon component.
 * 
 * Demonstrates boolean flag props for conditional rendering.
 */
export interface RefreshButtonIconProps {
  isLoading: boolean                           // Show loading or refresh icon
}

/**
 * Scroll anchor props.
 * 
 * Empty interface for marker component that maintains scroll position.
 */
export interface ScrollAnchorProps {
  // Marker component, no props needed
}

/**
 * Shadow overlay props for visual effects.
 * 
 * Uses literal types for position constraints.
 */
export interface ShadowOverlayProps {
  position: 'top' | 'bottom'                   // Literal type: only these two values allowed
}
