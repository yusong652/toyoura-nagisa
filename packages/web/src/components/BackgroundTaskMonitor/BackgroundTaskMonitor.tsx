/**
 * BackgroundTaskMonitor component - Terminal-style background task monitor.
 *
 * Displays active background bash processes with command-line aesthetics.
 * Positioned absolutely at the right side of chat container.
 *
 * Design:
 * - Minimalist terminal-style UI
 * - Shows only running tasks (completed tasks auto-hide after 5min)
 * - Displays command name + last 5 lines of output
 * - Collapsible panel to save screen space
 */
import React, { useState } from 'react'
import { useBackgroundTasks } from './hooks'
import { TaskItem } from './components'
import './BackgroundTaskMonitor.css'

/**
 * Main background task monitor component.
 *
 * Monitors background bash processes and displays them in a terminal-style
 * panel positioned at the right side of the chat container.
 *
 * Features:
 * - Auto-shows when tasks are running
 * - Collapsible to minimize screen usage
 * - Terminal aesthetics with monospace font
 * - Real-time output updates via WebSocket
 *
 * Returns:
 *     JSX element with floating task monitor panel, or null if no tasks
 */
const BackgroundTaskMonitor: React.FC = () => {
  const { activeTasks, activeCount } = useBackgroundTasks()
  const [collapsed, setCollapsed] = useState(false)

  // Hide panel when no active tasks
  if (activeCount === 0) {
    return null
  }

  return (
    <div className="bg-task-monitor">
      {/* Header with task count and collapse button */}
      <div className="bg-task-monitor-header">
        <div className="bg-task-monitor-title">
          <span className="bg-task-monitor-icon">$</span>
          <span className="bg-task-monitor-count">
            {activeCount} background {activeCount === 1 ? 'task' : 'tasks'}
          </span>
        </div>
        <button
          className="bg-task-monitor-collapse"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? '▼' : '▲'}
        </button>
      </div>

      {/* Task list */}
      {!collapsed && (
        <div className="bg-task-monitor-list">
          {activeTasks.map(task => (
            <TaskItem key={task.process_id} task={task} />
          ))}
        </div>
      )}
    </div>
  )
}

export default BackgroundTaskMonitor