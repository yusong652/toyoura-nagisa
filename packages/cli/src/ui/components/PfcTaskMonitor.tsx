/**
 * PFC Task Monitor Component
 *
 * Displays the current running PFC task in two lines.
 * Line 1: status indicator + description + runtime
 * Line 2: last output line (indented)
 *
 * Note: PFC only supports single-task execution.
 */

import React, { useState, useEffect } from 'react';
import { Text } from 'ink';
import { theme } from '../colors.js';
import type { PfcTask } from '../types/streamEvents.js';

/**
 * Format runtime duration
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
 * Truncate string with ellipsis
 */
function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength - 3) + '...';
}

export interface PfcTaskMonitorProps {
  currentTask: PfcTask | null;
}

export const PfcTaskMonitor: React.FC<PfcTaskMonitorProps> = ({ currentTask }) => {
  const [blink, setBlink] = useState(true);

  useEffect(() => {
    if (!currentTask || currentTask.status !== 'running') return;

    const interval = setInterval(() => {
      setBlink(prev => !prev);
    }, 500);

    return () => clearInterval(interval);
  }, [currentTask]);

  if (!currentTask || currentTask.status !== 'running') {
    return null;
  }

  const runtime = formatRuntime(currentTask.elapsed_time);
  const desc = currentTask.description || currentTask.script_name;
  const lastLine = currentTask.recent_output.length > 0
    ? currentTask.recent_output[currentTask.recent_output.length - 1].slice(0, 70)
    : '';

  return (
    <Text>
      <Text color={blink ? theme.task.indicator : theme.text.muted}>▶ </Text>
      <Text color={theme.task.title} inverse>PFC</Text>
      <Text color={theme.task.title}> {truncate(desc, 45)}</Text>
      <Text color={theme.task.meta}> ({runtime})</Text>
      {lastLine && (
        <>
          {'\n'}
          <Text color={theme.task.output}>  {lastLine}</Text>
        </>
      )}
    </Text>
  );
};
