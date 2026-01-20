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
import { PanelSection } from './shared/PanelSection.js';

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

  const effectiveTitleColor = borderColor || theme.text.primary;
  const titleTone = borderColor === theme.status.error ? 'error' : 'accent';

  // Loading state
  if (isLoading) {
    return (
      <PanelSection
        title={title}
        titlePrefix="?"
        tone={titleTone}
        paddingX={1}
        titleColor={effectiveTitleColor}
      >
        <Text color={theme.text.muted}>{loadingMessage}</Text>
      </PanelSection>
    );
  }

  // Empty state
  if (options.length === 0) {
    return (
      <PanelSection
        title={title}
        titlePrefix="?"
        tone={titleTone}
        paddingX={1}
        titleColor={effectiveTitleColor}
        contentGap={1}
      >
        <Text color={theme.text.muted}>{emptyMessage}</Text>
        <Text color={theme.text.muted}>(Press Esc to go back)</Text>
      </PanelSection>
    );
  }

  // Check if any option has a description
  const hasDescriptions = showDescriptions && options.some((o) => o.description);

  return (
    <PanelSection
      title={title}
      titlePrefix="?"
      tone={titleTone}
      paddingX={1}
      titleColor={effectiveTitleColor}
      description={description}
      descriptionColor={theme.text.secondary}
      contentGap={1}
    >
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
    </PanelSection>
  );
}
