/**
 * Todo Status Indicator Component
 * Displays current in-progress todo status above the input prompt.
 *
 * Shows what the AI agent is currently working on in real-time.
 * Only visible when streaming is active (matches web frontend behavior).
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { theme } from '../colors.js';
import type { TodoItem } from '../hooks/useTodoStatus.js';

// Advanced thinking verbs (AI, DEM simulation, geotechnical engineering, and playful ones)
// Reference: packages/web/src/components/TodoStatusIndicator/TodoStatusIndicator.tsx
const THINKING_VERBS = [
  'Reasoning',      // AI
  'Analyzing',      // General
  'Computing',      // Numerical
  'Simulating',     // DEM
  'Synthesizing',   // AI
  'Calibrating',    // Engineering
  'Iterating',      // Numerical
  'Evaluating',     // Analysis
  'Optimizing',     // Optimization
  'Converging',     // Numerical
  'Processing',     // Data
  'Interpreting',   // Analysis
  'Formulating',    // Problem solving
  'Orchestrating',  // AI coordination
  'Consolidating',  // Geotechnical - soil consolidation
  'Saturating',     // Geotechnical - soil saturation
  'Compacting',     // Geotechnical - soil compaction
  'Liquefying',     // Geotechnical - soil liquefaction
  'Bouncing',       // Playful - particle collision
  'Siliconizing',   // Playful - Toyoura sand reference (silicon dioxide)
  'Pondering',      // Playful - cute thinking
  'Tinkering',      // Playful - experimental
  'Daydreaming',    // Playful - very cute
  'Materializing',  // Playful - making things real
  'Crystallizing',  // Playful - forming structure (sand crystals)
  'Percolating',    // Playful - sand/fluid dynamics + coffee brewing
];

interface TodoStatusIndicatorProps {
  todo: TodoItem | null;
  isStreaming?: boolean;
}

export const TodoStatusIndicator: React.FC<TodoStatusIndicatorProps> = ({
  todo,
  isStreaming = false,
}) => {
  // Random thinking verb - changes when streaming starts
  const [thinkingVerb, setThinkingVerb] = useState(() =>
    THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)]
  );

  // Update thinking verb when streaming starts (new conversation turn)
  useEffect(() => {
    if (isStreaming) {
      setThinkingVerb(THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)]);
    }
  }, [isStreaming]);

  // Only show when streaming is active (matches web frontend behavior)
  // The todo prop only affects display text, not visibility
  // Reference: packages/web/src/components/TodoStatusIndicator/TodoStatusIndicator.tsx:83
  if (!isStreaming) {
    return null;
  }

  // Get the display text: todo's activeForm or random thinking verb
  const displayText = todo?.activeForm || thinkingVerb;

  return (
    <Box paddingLeft={1} marginBottom={0}>
      <Text color={theme.ui.spinner}>
        <Spinner type="dots" />
        {' '}{displayText}...
      </Text>
    </Box>
  );
};
