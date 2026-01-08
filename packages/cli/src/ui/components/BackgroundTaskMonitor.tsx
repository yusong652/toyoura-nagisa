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
  const displayCommand = task.description || truncateCommand(task.command);

  return (
    <Box flexDirection="column" marginLeft={2}>
      {/* Task header: [status] id | runtime | command */}
      <Box>
        <Text color={color}>[{indicator}]</Text>
        <Text color={theme.text.secondary}> {task.process_id} | </Text>
        <Text color={theme.text.accent}>{runtime}</Text>
        <Text color={theme.text.secondary}> | </Text>
        <Text color={theme.text.primary}>{displayCommand}</Text>
      </Box>

      {/* Recent output (only for running tasks with output) */}
      {task.status === 'running' && task.recent_output.length > 0 && (
        <Box flexDirection="column" marginLeft={2} marginTop={0}>
          {task.recent_output.slice(-3).map((line, index) => (
            <Text key={index} color={theme.text.secondary} dimColor>
              {line.slice(0, 60)}{line.length > 60 ? '...' : ''}
            </Text>
          ))}
        </Box>
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
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={theme.border.default}
      paddingX={1}
      marginBottom={1}
    >
      {/* Header */}
      <Box>
        <Text color={theme.status.info}>$</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.text.primary}>
          {activeCount} background {activeCount === 1 ? 'task' : 'tasks'}
        </Text>
      </Box>

      {/* Task list */}
      {sortedTasks.map(task => (
        <TaskItem key={task.process_id} task={task} />
      ))}
    </Box>
  );
};
