/**
 * ChatBox title bar component with refresh functionality.
 * 
 * This component demonstrates:
 * - Conditional rendering based on props
 * - Async event handlers in React
 * - Accessibility attributes (aria-label, title)
 * - SVG icon rendering with conditional display
 */

import React from 'react'
import { ChatBoxTitleBarProps } from '../types'

/**
 * Renders the title bar for the ChatBox with session title and refresh button.
 * 
 * Features:
 * - Displays current session title
 * - Refresh button with loading state
 * - Disabled state with helpful tooltips
 * - Accessible button with proper ARIA labels
 * 
 * Args:
 *     currentSessionTitle: Title text to display
 *     currentSessionId: Session ID for conditional rendering
 *     isRefreshingTitle: Loading state for button
 *     canRefreshTitle: Whether refresh is allowed
 *     onRefreshTitle: Async handler for refresh action
 * 
 * TypeScript Learning Points:
 * - React.FC<Props> for functional component typing
 * - Conditional rendering with && operator
 * - Template literals for dynamic class names
 * - Async function props handling
 */
const ChatBoxTitleBar: React.FC<ChatBoxTitleBarProps> = ({
  currentSessionTitle,
  currentSessionId,
  isRefreshingTitle,
  canRefreshTitle,
  onRefreshTitle
}) => {
  return (
    <div className="chatbox-title-bar">
      <h2 className="chatbox-title">
        {currentSessionTitle}
        {currentSessionId && (
          <button 
            className={`refresh-title-button ${isRefreshingTitle ? 'loading' : ''} ${!canRefreshTitle ? 'disabled' : ''}`}
            onClick={onRefreshTitle}
            disabled={isRefreshingTitle || !canRefreshTitle}
            title={canRefreshTitle 
              ? "Refresh Title" 
              : "Need at least one user message and one AI reply to refresh title"}
            aria-label="Refresh Title"
          >
            {isRefreshingTitle ? (
              // Loading spinner icon
              <svg 
                xmlns="http://www.w3.org/2000/svg" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 6v6l4 2"></path>
              </svg>
            ) : (
              // Refresh icon
              <svg 
                xmlns="http://www.w3.org/2000/svg" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              >
                <path d="M21 2v6h-6"></path>
                <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path>
                <path d="M3 22v-6h6"></path>
                <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path>
              </svg>
            )}
          </button>
        )}
      </h2>
    </div>
  )
}

export default ChatBoxTitleBar

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Conditional Rendering:
 *    currentSessionId && (...) - TypeScript understands null check
 * 
 * 2. Template Literals:
 *    `refresh-title-button ${isRefreshingTitle ? 'loading' : ''}`
 * 
 * 3. Ternary Operators:
 *    canRefreshTitle ? "text1" : "text2" - Type-safe conditionals
 * 
 * 4. Boolean Props:
 *    disabled={isRefreshingTitle || !canRefreshTitle}
 * 
 * 5. Event Handler Props:
 *    onClick={onRefreshTitle} - Function prop typing
 * 
 * 6. SVG in TSX:
 *    Proper typing for SVG attributes (strokeWidth as number or string)
 */