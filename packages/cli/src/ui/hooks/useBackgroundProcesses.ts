/**
 * Background Processes Hook
 *
 * Listens to background_process_notification events from ConnectionManager
 * and maintains a map of active background tasks. Provides task list for
 * terminal UI display.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import type { BackgroundTask, BackgroundProcessNotificationEvent } from '../types/streamEvents.js';

/**
 * Hook options
 */
export interface UseBackgroundProcessesOptions {
  connectionManager: ConnectionManager;
  /** Cleanup delay for completed tasks in milliseconds (default: 5 minutes) */
  cleanupDelayMs?: number;
}

/**
 * Hook return type
 */
export interface UseBackgroundProcessesReturn {
  /** All background tasks */
  tasks: BackgroundTask[];
  /** Only running tasks */
  activeTasks: BackgroundTask[];
  /** Only completed/killed tasks */
  completedTasks: BackgroundTask[];
  /** Number of running tasks */
  activeCount: number;
}

/**
 * Manage background process state and lifecycle.
 *
 * Subscribes to 'background_process_notification' events from ConnectionManager
 * and maintains task state. Automatically cleans up old completed tasks.
 *
 * Example:
 *     const { activeTasks, activeCount } = useBackgroundProcesses({
 *       connectionManager
 *     })
 *     console.log(`${activeCount} tasks running`)
 */
export function useBackgroundProcesses({
  connectionManager,
  cleanupDelayMs = 5 * 60 * 1000, // 5 minutes default
}: UseBackgroundProcessesOptions): UseBackgroundProcessesReturn {
  const [taskMap, setTaskMap] = useState<Map<string, BackgroundTask>>(new Map());

  // Track cleanup timeouts to clear on unmount
  const cleanupTimeoutsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Handle notification event
  const handleNotification = useCallback((data: BackgroundProcessNotificationEvent) => {
    setTaskMap(prevMap => {
      const newMap = new Map(prevMap);

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
        timestamp: data.timestamp || new Date().toISOString(),
      };

      newMap.set(data.process_id, task);

      // Schedule cleanup for completed/killed tasks
      if (data.status === 'completed' || data.status === 'killed') {
        // Clear any existing timeout for this process
        const existingTimeout = cleanupTimeoutsRef.current.get(data.process_id);
        if (existingTimeout) {
          clearTimeout(existingTimeout);
        }

        // Schedule new cleanup
        const timeout = setTimeout(() => {
          setTaskMap(currentMap => {
            const updatedMap = new Map(currentMap);
            updatedMap.delete(data.process_id);
            return updatedMap;
          });
          cleanupTimeoutsRef.current.delete(data.process_id);
        }, cleanupDelayMs);

        cleanupTimeoutsRef.current.set(data.process_id, timeout);
      }

      return newMap;
    });
  }, [cleanupDelayMs]);

  // Subscribe to ConnectionManager events
  useEffect(() => {
    connectionManager.on('background_process_notification', handleNotification);

    return () => {
      connectionManager.off('background_process_notification', handleNotification);

      // Clear all cleanup timeouts on unmount
      cleanupTimeoutsRef.current.forEach(timeout => clearTimeout(timeout));
      cleanupTimeoutsRef.current.clear();
    };
  }, [connectionManager, handleNotification]);

  // Convert map to arrays and categorize
  const tasks = Array.from(taskMap.values());
  const activeTasks = tasks.filter(t => t.status === 'running');
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'killed');

  return {
    tasks,
    activeTasks,
    completedTasks,
    activeCount: activeTasks.length,
  };
}
