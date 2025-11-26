/**
 * Generic Select Dialog Component
 *
 * A reusable dialog for selecting from a list of options.
 * Uses RadioButtonSelect for keyboard navigation and selection.
 */

import React, { useCallback } from 'react';
import { Box, Text } from 'ink';
import { RadioButtonSelect, type RadioSelectItem } from './shared/RadioButtonSelect.js';
import { theme } from '../colors.js';
import { useKeypress } from '../hooks/useKeypress.js';

export interface SelectOption<T> extends RadioSelectItem<T> {
  description: string;
}

interface SelectDialogProps<T> {
  /** Dialog title */
  title: string;
  /** Description text below title */
  description: string;
  /** Available options */
  options: readonly SelectOption<T>[];
  /** Current selected value */
  currentValue: T;
  /** Callback when an option is selected */
  onSelect: (value: T) => void;
  /** Callback when dialog is cancelled */
  onCancel: () => void;
  /** Whether to show option numbers */
  showNumbers?: boolean;
}

export function SelectDialog<T>({
  title,
  description,
  options,
  currentValue,
  onSelect,
  onCancel,
  showNumbers = false,
}: SelectDialogProps<T>): React.ReactElement {
  // Find initial index based on current value
  const initialIndex = options.findIndex((o) => o.value === currentValue);

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

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.focused}
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
        maxItemsToShow={options.length}
      />

      {/* Option descriptions */}
      <Box marginTop={1} flexDirection="column">
        {options.map((option) => (
          <Box key={option.key}>
            <Text color={theme.text.muted}>
              {option.label}: {option.description}
            </Text>
          </Box>
        ))}
      </Box>

      {/* Help text */}
      <Box marginTop={1}>
        <Text color={theme.text.muted}>
          (Use arrows to navigate, Enter to select, Esc to cancel)
        </Text>
      </Box>
    </Box>
  );
}
