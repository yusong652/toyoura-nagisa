/**
 * Background Task Monitor Component
 *
 * Displays running background bash tasks in a compact terminal-friendly format.
 * Shows task ID, command, status, and recent output.
 */

import React, { useMemo, useState, useEffect } from 'react';
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
 * Single task item display
 */
interface TaskItemProps {
  task: BackgroundTask;
  blink: boolean;
}

const TaskItem: React.FC<TaskItemProps> = ({ task, blink }) => {
  const runtime = formatRuntime(task.runtime_seconds);
  const displayCommand = truncateCommand(task.description || task.command, 50);

  // Get last line of output
  const lastOutput = task.recent_output.length > 0
    ? task.recent_output[task.recent_output.length - 1].slice(0, 70)
    : '';

  // Blink effect: task indicator ↔ muted
  const indicatorColor = blink ? theme.task.indicator : theme.text.muted;

  return (
    <Box flexDirection="column">
      {/* Line 1: symbol label command runtime */}
      <Box>
        <Text color={indicatorColor}>▶ </Text>
        <Text color={theme.task.title} inverse>Bash</Text>
        <Text color={theme.task.title}> {displayCommand}</Text>
        <Text color={theme.task.meta}> ({runtime})</Text>
      </Box>
      {/* Line 2: output (if any) */}
      {lastOutput && (
        <Box marginLeft={2}>
          <Text color={theme.task.output}>{lastOutput}</Text>
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
  const [blink, setBlink] = useState(true);

  // Blink effect for running tasks
  useEffect(() => {
    if (activeCount === 0) return;

    const interval = setInterval(() => {
      setBlink(prev => !prev);
    }, 500);

    return () => clearInterval(interval);
  }, [activeCount]);

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
    <>
      {sortedTasks.map(task => (
        <TaskItem key={task.process_id} task={task} blink={blink} />
      ))}
    </>
  );
};
