/**
 * Suggestions Display Component
 * Reference: Gemini CLI ui/components/SuggestionsDisplay.tsx
 *
 * Renders autocomplete suggestions popup for slash commands.
 * Supports navigation, scrolling, and visual feedback for active selection.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';

// Maximum suggestions to show at once
export const MAX_SUGGESTIONS_TO_SHOW = 8;

export interface Suggestion {
  /** Display label */
  label: string;
  /** Value to insert on selection */
  value: string;
  /** Optional description */
  description?: string;
}

interface SuggestionsDisplayProps {
  suggestions: Suggestion[];
  activeIndex: number;
  isLoading: boolean;
  scrollOffset: number;
}

export const SuggestionsDisplay: React.FC<SuggestionsDisplayProps> = ({
  suggestions,
  activeIndex,
  isLoading,
  scrollOffset,
}) => {
  if (isLoading) {
    return (
      <Box paddingX={1}>
        <Text color={theme.text.muted}>Loading suggestions...</Text>
      </Box>
    );
  }

  if (suggestions.length === 0) {
    return null;
  }

  // Calculate visible slice based on scrollOffset
  const startIndex = scrollOffset;
  const endIndex = Math.min(
    scrollOffset + MAX_SUGGESTIONS_TO_SHOW,
    suggestions.length
  );
  const visibleSuggestions = suggestions.slice(startIndex, endIndex);

  // Calculate column width for alignment (use all suggestions for consistent width)
  const maxLabelWidth = Math.max(
    ...suggestions.map((s) => s.label.length),
    8 // minimum width
  );

  return (
    <Box flexDirection="column" paddingX={1}>
      {/* Up scroll indicator */}
      {scrollOffset > 0 && <Text color={theme.text.primary}>▲</Text>}

      {/* Suggestions list */}
      {visibleSuggestions.map((suggestion, index) => {
        const originalIndex = startIndex + index;
        const isActive = originalIndex === activeIndex;
        const textColor = isActive ? theme.text.accent : theme.text.secondary;

        return (
          <Box key={`${suggestion.value}-${originalIndex}`} flexDirection="row">
            {/* Command name with slash */}
            <Box width={maxLabelWidth + 2} flexShrink={0}>
              <Text color={textColor} bold={isActive}>
                /{suggestion.label}
              </Text>
            </Box>

            {/* Description */}
            {suggestion.description && (
              <Box flexGrow={1} paddingLeft={2}>
                <Text color={textColor} wrap="truncate">
                  {suggestion.description}
                </Text>
              </Box>
            )}
          </Box>
        );
      })}

      {/* Down scroll indicator */}
      {endIndex < suggestions.length && <Text color={theme.text.muted}>▼</Text>}

      {/* Page indicator - always show total count */}
      <Text color={theme.text.muted}>
        ({activeIndex + 1}/{suggestions.length})
      </Text>
    </Box>
  );
};
