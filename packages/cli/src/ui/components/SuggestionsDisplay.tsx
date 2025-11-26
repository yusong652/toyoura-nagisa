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
const MAX_SUGGESTIONS_TO_SHOW = 6;

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
  width?: number;
}

export const SuggestionsDisplay: React.FC<SuggestionsDisplayProps> = ({
  suggestions,
  activeIndex,
  isLoading,
  scrollOffset,
  width,
}) => {
  if (isLoading) {
    return (
      <Box paddingX={1} width={width}>
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

  // Calculate column width for alignment
  const maxLabelWidth = Math.max(
    ...visibleSuggestions.map((s) => s.label.length),
    8 // minimum width
  );

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={theme.border.default}
      paddingX={1}
      width={width}
    >
      {/* Header */}
      <Box marginBottom={0}>
        <Text color={theme.text.muted} dimColor>
          Commands ({suggestions.length})
        </Text>
      </Box>

      {/* Suggestions list */}
      {visibleSuggestions.map((suggestion, index) => {
        const originalIndex = startIndex + index;
        const isActive = originalIndex === activeIndex;

        return (
          <Box key={`${suggestion.value}-${originalIndex}`} flexDirection="row">
            {/* Selection indicator */}
            <Box width={2}>
              <Text color={isActive ? theme.text.accent : theme.text.muted}>
                {isActive ? '>' : ' '}
              </Text>
            </Box>

            {/* Command name */}
            <Box width={maxLabelWidth + 2}>
              <Text
                color={isActive ? theme.text.accent : theme.text.primary}
                bold={isActive}
              >
                /{suggestion.label}
              </Text>
            </Box>

            {/* Description */}
            {suggestion.description && (
              <Box flexGrow={1}>
                <Text
                  color={isActive ? theme.text.secondary : theme.text.muted}
                  wrap="truncate"
                >
                  {suggestion.description}
                </Text>
              </Box>
            )}
          </Box>
        );
      })}

      {/* Scroll indicator */}
      {suggestions.length > MAX_SUGGESTIONS_TO_SHOW && (
        <Box marginTop={0}>
          <Text color={theme.text.muted} dimColor>
            [{startIndex + 1}-{endIndex}/{suggestions.length}] Use arrows to navigate
          </Text>
        </Box>
      )}
    </Box>
  );
};

export { MAX_SUGGESTIONS_TO_SHOW };
