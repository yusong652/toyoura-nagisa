/**
 * Background Task Monitor Component
 *
 * Displays running background bash tasks in a compact terminal-friendly format.
 * Shows task ID, command, status, and recent output.
 */

import React, { useMemo } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';
import type { BackgroundTask } from '../types/streamEvents.js';

/**
 * Format runtime duration in human-readable form
 */
function formatRuntime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (minutes < 60) {
    return `${minutes}m${secs}s`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h${mins}m`;
}

/**
 * Truncate command string for display
 */
function truncateCommand(command: string, maxLength: number = 40): string {
  if (command.length <= maxLength) {
    return command;
  }
  return command.slice(0, maxLength - 3) + '...';
}

/**
 * Get status indicator and color
 */
function getStatusDisplay(status: BackgroundTask['status'], exitCode?: number): {
  indicator: string;
  color: string;
} {
  switch (status) {
    case 'running':
      return { indicator: '...', color: theme.status.info };
    case 'completed':
      if (exitCode === 0) {
        return { indicator: 'OK', color: theme.status.success };
      }
      return { indicator: `X${exitCode}`, color: theme.status.error };
    case 'killed':
      return { indicator: 'KILL', color: theme.status.warning };
    default:
      return { indicator: '?', color: theme.text.secondary };
  }
}

/**
 * Single task item display
 */
interface TaskItemProps {
  task: BackgroundTask;
}

const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  const { indicator, color } = getStatusDisplay(task.status, task.exit_code);
  const runtime = formatRuntime(task.runtime_seconds);
  const displayCommand = task.description || truncateCommand(task.command, 50);

  // Get last line of output for inline display
  const lastOutput = task.recent_output.length > 0
    ? task.recent_output[task.recent_output.length - 1].slice(0, 40)
    : '';

  return (
    <Box>
      {/* Compact single-line format: [status] id runtime command (output) */}
      <Text color={theme.text.secondary}>[</Text>
      <Text color={color}>{indicator}</Text>
      <Text color={theme.text.secondary}>] </Text>
      <Text color={theme.text.muted}>{task.process_id}</Text>
      <Text color={theme.text.secondary}> </Text>
      <Text color={theme.text.accent}>{runtime}</Text>
      <Text color={theme.text.secondary}> </Text>
      <Text color={theme.text.primary}>{displayCommand}</Text>
      {lastOutput && (
        <>
          <Text color={theme.text.secondary}> | </Text>
          <Text color={theme.text.muted} dimColor>{lastOutput}</Text>
        </>
      )}
    </Box>
  );
};

/**
 * Background Task Monitor Props
 */
export interface BackgroundTaskMonitorProps {
  /** List of active (running) tasks */
  activeTasks: BackgroundTask[];
  /** Number of active tasks */
  activeCount: number;
}

/**
 * Background Task Monitor
 *
 * Displays a compact view of running background tasks.
 * Hidden when no tasks are running.
 */
export const BackgroundTaskMonitor: React.FC<BackgroundTaskMonitorProps> = ({
  activeTasks,
  activeCount,
}) => {
  // Sort tasks by start time (oldest first)
  const sortedTasks = useMemo(() => {
    return [...activeTasks].sort((a, b) => {
      return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
    });
  }, [activeTasks]);

  // Hide when no active tasks
  if (activeCount === 0) {
    return null;
  }

  return (
    <Box flexDirection="column">
      {/* Task list - compact inline format */}
      {sortedTasks.map(task => (
        <TaskItem key={task.process_id} task={task} />
      ))}
    </Box>
  );
};
