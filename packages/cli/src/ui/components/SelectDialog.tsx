/**
 * Generic Select Dialog Component
 *
 * A reusable dialog for selecting from a list of options.
 * Uses RadioButtonSelect for keyboard navigation and selection.
 * Supports loading state and dynamic options.
 */

import React, { useCallback } from 'react';
import { Box, Text } from 'ink';
import { RadioButtonSelect, type RadioSelectItem } from './shared/RadioButtonSelect.js';
import { theme } from '../colors.js';
import { useKeypress } from '../hooks/useKeypress.js';

export interface SelectOption<T> extends RadioSelectItem<T> {
  description?: string;
}

interface SelectDialogProps<T> {
  /** Dialog title */
  title: string;
  /** Description text below title */
  description: string;
  /** Available options */
  options: readonly SelectOption<T>[];
  /** Current selected value (optional for dynamic lists) */
  currentValue?: T;
  /** Callback when an option is selected */
  onSelect: (value: T) => void;
  /** Callback when dialog is cancelled */
  onCancel: () => void;
  /** Whether to show option numbers */
  showNumbers?: boolean;
  /** Whether options are loading */
  isLoading?: boolean;
  /** Loading message */
  loadingMessage?: string;
  /** Empty message when no options */
  emptyMessage?: string;
  /** Whether to show option descriptions below the list */
  showDescriptions?: boolean;
  /** Maximum items to show (for scrolling) */
  maxItemsToShow?: number;
  /** Border color override (e.g., for danger dialogs) */
  borderColor?: string;
}

export function SelectDialog<T>({
  title,
  description,
  options,
  currentValue,
  onSelect,
  onCancel,
  showNumbers = false,
  isLoading = false,
  loadingMessage = 'Loading...',
  emptyMessage = 'No options available.',
  showDescriptions = true,
  maxItemsToShow,
  borderColor,
}: SelectDialogProps<T>): React.ReactElement {
  // Find initial index based on current value
  const initialIndex = currentValue !== undefined
    ? options.findIndex((o) => o.value === currentValue)
    : 0;

  // Handle selection
  const handleSelect = useCallback(
    (value: T) => {
      onSelect(value);
    },
    [onSelect]
  );

  // Handle escape key to cancel
  useKeypress(
    (key) => {
      if (key.name === 'escape') {
        onCancel();
      }
    },
    { isActive: true }
  );

  const effectiveBorderColor = borderColor || theme.border.focused;

  // Loading state
  if (isLoading) {
    return (
      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor={effectiveBorderColor}
        paddingX={1}
        paddingY={0}
      >
        <Box marginBottom={1}>
          <Text color={theme.text.accent}>? </Text>
          <Text bold color={theme.text.primary}>{title}</Text>
        </Box>
        <Text color={theme.text.muted}>{loadingMessage}</Text>
      </Box>
    );
  }

  // Empty state
  if (options.length === 0) {
    return (
      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor={effectiveBorderColor}
        paddingX={1}
        paddingY={0}
      >
        <Box marginBottom={1}>
          <Text color={theme.text.accent}>? </Text>
          <Text bold color={theme.text.primary}>{title}</Text>
        </Box>
        <Text color={theme.text.muted}>{emptyMessage}</Text>
        <Box marginTop={1}>
          <Text color={theme.text.muted}>(Press Esc to go back)</Text>
        </Box>
      </Box>
    );
  }

  // Check if any option has a description
  const hasDescriptions = showDescriptions && options.some((o) => o.description);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={effectiveBorderColor}
      paddingX={1}
      paddingY={0}
    >
      {/* Title */}
      <Box marginBottom={1}>
        <Text color={theme.text.accent}>? </Text>
        <Text bold color={theme.text.primary}>
          {title}
        </Text>
      </Box>

      {/* Description */}
      <Box marginBottom={1}>
        <Text color={theme.text.secondary}>{description}</Text>
      </Box>

      {/* Options list */}
      <RadioButtonSelect
        items={options as SelectOption<T>[]}
        initialIndex={initialIndex >= 0 ? initialIndex : 0}
        onSelect={handleSelect}
        showNumbers={showNumbers}
        maxItemsToShow={maxItemsToShow ?? options.length}
      />

      {/* Option descriptions (only if showDescriptions and options have descriptions) */}
      {hasDescriptions && (
        <Box marginTop={1} flexDirection="column">
          {options.map((option) => (
            option.description && (
              <Box key={option.key}>
                <Text color={theme.text.muted}>
                  {option.label}: {option.description}
                </Text>
              </Box>
            )
          ))}
        </Box>
      )}

      {/* Help text */}
      <Box marginTop={1}>
        <Text color={theme.text.muted}>
          (Use arrows to navigate, Enter to select, Esc to cancel)
        </Text>
      </Box>
    </Box>
  );
}
