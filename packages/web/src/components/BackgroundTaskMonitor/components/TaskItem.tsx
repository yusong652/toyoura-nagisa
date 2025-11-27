/**
 * TaskItem component - Terminal-style background task display.
 *
 * Displays a single background bash task with command-line aesthetics:
 * - Command name with status indicator
 * - Recent 5 lines of output in monospace font
 * - Runtime counter
 * - Exit code for completed tasks
 */
import React from 'react'
import { BackgroundTask } from '../types'

interface TaskItemProps {
  task: BackgroundTask
}

/**
 * Format runtime seconds to human-readable string.
 *
 * Args:
 *     seconds: Runtime in seconds
 *
 * Returns:
 *     Formatted string (e.g., "5s", "1m 23s", "1h 5m")
 */
const formatRuntime = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}m ${secs}s`
  } else {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${mins}m`
  }
}

/**
 * Get status symbol for terminal display.
 *
 * Args:
 *     status: Task status
 *
 * Returns:
 *     Status symbol string
 */
const getStatusSymbol = (status: string): string => {
  switch (status) {
    case 'running':
      return '●'  // Running indicator
    case 'completed':
      return '✓'  // Completed checkmark
    case 'killed':
      return '✗'  // Killed cross
    default:
      return '○'
  }
}

/**
 * TaskItem component with terminal aesthetics.
 *
 * Displays background task with command-line styling for clean,
 * technical appearance that matches bash execution context.
 *
 * Props:
 *     task: BackgroundTask object with process information
 *
 * Returns:
 *     JSX element with terminal-styled task display
 */
const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  return (
    <div className="bg-task-item">
      {/* Header: Command + Status */}
      <div className="bg-task-header">
        <span className={`bg-task-status bg-task-status-${task.status}`}>
          {getStatusSymbol(task.status)}
        </span>
        <span className="bg-task-command">{task.command}</span>
        <span className="bg-task-runtime">{formatRuntime(task.runtime_seconds)}</span>
      </div>

      {/* Output viewport - Last 5 lines */}
      {task.recent_output.length > 0 && (
        <div className="bg-task-output">
          {task.recent_output.map((line, index) => (
            <div key={index} className="bg-task-output-line">
              {line}
            </div>
          ))}
          {task.has_more_output && (
            <div className="bg-task-output-more">...</div>
          )}
        </div>
      )}

      {/* Footer: Exit code for completed tasks */}
      {task.status !== 'running' && task.exit_code !== undefined && (
        <div className="bg-task-footer">
          <span className="bg-task-exit-code">
            exit {task.exit_code}
          </span>
        </div>
      )}
    </div>
  )
}

export default TaskItem