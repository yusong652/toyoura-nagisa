/**
 * Custom hook for managing background task state.
 *
 * Listens to WebSocket events from ConnectionContext and maintains
 * a map of active background tasks. Provides task list and utilities
 * for task management.
 */
import { useState, useEffect } from 'react'
import { BackgroundTask, BackgroundProcessNotificationEvent } from '../types'

/**
 * Hook return type with task state and utilities.
 */
interface UseBackgroundTasksReturn {
  tasks: BackgroundTask[]               // Array of all tasks
  activeTasks: BackgroundTask[]         // Only running tasks
  completedTasks: BackgroundTask[]      // Only completed/killed tasks
  activeCount: number                   // Number of running tasks
}

/**
 * Manage background task state and lifecycle.
 *
 * Subscribes to 'backgroundProcessNotification' events from ConnectionContext
 * and maintains task state. Automatically cleans up old completed tasks.
 *
 * Returns:
 *     Object containing:
 *     - tasks: All background tasks
 *     - activeTasks: Currently running tasks
 *     - completedTasks: Completed or killed tasks
 *     - activeCount: Number of running tasks
 *
 * Example:
 *     const { tasks, activeCount } = useBackgroundTasks()
 *     console.log(`${activeCount} tasks running`)
 */
export const useBackgroundTasks = (): UseBackgroundTasksReturn => {
  const [taskMap, setTaskMap] = useState<Map<string, BackgroundTask>>(new Map())

  useEffect(() => {
    /**
     * Handle background process notification events.
     *
     * Updates task state based on notification type and data.
     */
    const handleNotification = (event: Event) => {
      const customEvent = event as CustomEvent<BackgroundProcessNotificationEvent>
      const data = customEvent.detail

      console.log('[useBackgroundTasks] Received notification:', data)

      setTaskMap(prevMap => {
        const newMap = new Map(prevMap)

        // Create or update task
        const task: BackgroundTask = {
          process_id: data.process_id,
          command: data.command,
          description: data.description,
          status: data.status,
          recent_output: data.recent_output || [],
          has_more_output: data.has_more_output || false,
          runtime_seconds: data.runtime_seconds || 0,
          exit_code: data.exit_code,
          timestamp: data.timestamp || new Date().toISOString()
        }

        newMap.set(data.process_id, task)

        // Auto-cleanup completed tasks after 5 minutes
        if (data.status === 'completed' || data.status === 'killed') {
          setTimeout(() => {
            setTaskMap(currentMap => {
              const updatedMap = new Map(currentMap)
              updatedMap.delete(data.process_id)
              return updatedMap
            })
          }, 5 * 60 * 1000) // 5 minutes
        }

        return newMap
      })
    }

    // Subscribe to background process notifications
    window.addEventListener('backgroundProcessNotification', handleNotification)

    return () => {
      window.removeEventListener('backgroundProcessNotification', handleNotification)
    }
  }, [])

  // Convert map to arrays and categorize
  const tasks = Array.from(taskMap.values())
  const activeTasks = tasks.filter(t => t.status === 'running')
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'killed')

  return {
    tasks,
    activeTasks,
    completedTasks,
    activeCount: activeTasks.length
  }
}