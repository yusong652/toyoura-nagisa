/**
 * PFC Tasks Hook
 *
 * Listens to pfc_task_notification events from ConnectionManager
 * and maintains state for the current PFC task. Since PFC only supports
 * single-task execution, this is simpler than useBackgroundProcesses.
 */

import { useState, useEffect, useCallback } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import type { PfcTask, PfcTaskNotificationEvent } from '../types/streamEvents.js';

/**
 * Hook options
 */
export interface UsePfcTasksOptions {
  connectionManager: ConnectionManager;
}

/**
 * Hook return type
 */
export interface UsePfcTasksReturn {
  /** Current PFC task (null if none) */
  currentTask: PfcTask | null;
  /** Whether a task is currently running */
  isRunning: boolean;
}

/**
 * Manage PFC task state.
 *
 * Subscribes to 'pfc_task_notification' events from ConnectionManager
 * and maintains state for the current running task.
 *
 * Note: PFC only supports single-task execution, so we only track one task.
 *
 * Example:
 *     const { currentTask, isRunning } = usePfcTasks({ connectionManager })
 *     if (isRunning) {
 *       console.log(`Running: ${currentTask.description}`)
 *     }
 */
export function usePfcTasks({
  connectionManager,
}: UsePfcTasksOptions): UsePfcTasksReturn {
  const [currentTask, setCurrentTask] = useState<PfcTask | null>(null);

  // Handle notification event
  const handleNotification = useCallback((data: PfcTaskNotificationEvent) => {
    // Only track running tasks
    if (data.status === 'running') {
      const task: PfcTask = {
        task_id: data.task_id,
        session_id: data.session_id,
        script_name: data.script_name,
        description: data.description || '',
        status: data.status,
        source: data.source || 'agent',
        recent_output: data.recent_output || [],
        has_more_output: data.has_more_output || false,
        start_time: data.start_time,
        elapsed_time: data.elapsed_time || 0,
        git_commit: data.git_commit,
        error: data.error,
      };
      setCurrentTask(task);
    } else {
      // Task completed/failed/interrupted - clear it
      setCurrentTask(null);
    }
  }, []);

  // Subscribe to ConnectionManager events
  useEffect(() => {
    connectionManager.on('pfc_task_notification', handleNotification);

    return () => {
      connectionManager.off('pfc_task_notification', handleNotification);
    };
  }, [connectionManager, handleNotification]);

  return {
    currentTask,
    isRunning: currentTask !== null && currentTask.status === 'running',
  };
}
