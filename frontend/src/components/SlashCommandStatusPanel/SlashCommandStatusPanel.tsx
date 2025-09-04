import React from 'react'
import { CommandExecutionTask } from '../InputArea/types'
import { StatusSpinnerIcon, ErrorIcon } from '../InputArea/styles/icons'
import './SlashCommandStatusPanel.css'

/**
 * Independent status panel for slash command execution feedback.
 * 
 * This component is separated from InputArea to maintain clean separation of concerns:
 * - InputArea handles user input and interaction
 * - SlashCommandStatusPanel handles command execution feedback
 * 
 * Features:
 * - Displays queue of executing commands
 * - Shows progress indicators with spinners
 * - Handles multiple concurrent commands
 * - Smooth animations for status changes
 * 
 * Architecture Benefits:
 * - Single responsibility: only command status display
 * - Reusable: can be positioned anywhere in the UI
 * - Independent: doesn't interfere with input functionality
 * - Maintainable: clear separation from input logic
 */

interface SlashCommandStatusPanelProps {
  executionQueue: CommandExecutionTask[]
  className?: string
  position?: 'top-right' | 'bottom-right' | 'floating' | 'chatbox-right'
}

const SlashCommandStatusPanel: React.FC<SlashCommandStatusPanelProps> = ({
  executionQueue,
  className = '',
  position = 'floating'
}) => {
  // Don't render if no commands are executing
  if (executionQueue.length === 0) {
    return null
  }

  /**
   * Truncate error message with ellipsis if too long
   * Responsive truncation based on screen size
   * @param message - Error message to truncate
   * @returns Truncated message with ellipsis if needed
   */
  const truncateMessage = (message: string): string => {
    // Check if we're on mobile (simplified approach)
    const isMobile = window.innerWidth <= 768
    const maxLength = isMobile ? 25 : 40
    
    if (message.length <= maxLength) return message
    return message.substring(0, maxLength).trim() + '...'
  }

  return (
    <div className={`slash-command-status-panel ${position} ${className}`.trim()}>
      {executionQueue.map((task, index) => {
        const isError = task.status === 'error'
        return (
          <div key={task.id} className={`command-status-item ${isError ? 'error' : ''}`.trim()}>
            {isError ? (
              <ErrorIcon size={16} className="command-error-icon" />
            ) : (
              <StatusSpinnerIcon size={16} className="command-spinner" />
            )}
            <span 
              className="command-status-label"
              title={isError && task.error ? `failed ${task.command.trigger}: ${task.error}` : undefined}
            >
              {isError ? (
                <>
                  failed {task.command.trigger}
                  {task.error ? `: ${truncateMessage(task.error)}` : ''}
                </>
              ) : (
                <>
                  generating {task.command.trigger}
                  {executionQueue.length > 1 && (
                    <span className="queue-position">
                      ({index + 1}/{executionQueue.length})
                    </span>
                  )}
                </>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default SlashCommandStatusPanel

/**
 * TypeScript Learning Points:
 * 
 * 1. **Props Interface Design**:
 *    - Optional className for styling flexibility
 *    - Position prop with literal union type for predefined layouts
 *    - CommandExecutionTask array for queue data
 * 
 * 2. **Conditional Rendering**:
 *    - Early return pattern for empty queue
 *    - Conditional queue position display based on array length
 * 
 * 3. **Component Composition**:
 *    - Reuses existing StatusSpinnerIcon component
 *    - Clean props threading for customization
 * 
 * 4. **CSS Integration**:
 *    - Dynamic className generation based on props
 *    - Position-based styling through CSS classes
 * 
 * Architecture Benefits:
 * - **Single Responsibility**: Only handles command status display
 * - **Separation of Concerns**: InputArea focuses on input, this handles feedback
 * - **Reusability**: Can be positioned anywhere in the application
 * - **Maintainability**: Changes to status display don't affect input logic
 * - **Testability**: Easy to test status display logic in isolation
 */
