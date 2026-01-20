/**
 * Slash Command Suggestions Component
 * Reference: Gemini CLI ui/components/SuggestionsDisplay.tsx
 *
 * Renders autocomplete suggestions popup for slash commands.
 * Supports navigation, scrolling, and visual feedback for active selection.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme, colors } from '../colors.js';
import { PanelSection } from './shared/PanelSection.js';

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

export const SlashCommandSuggestions: React.FC<SuggestionsDisplayProps> = ({
  suggestions,
  activeIndex,
  isLoading,
  scrollOffset,
}) => {
  if (isLoading) {
    return (
      <PanelSection
        paddingX={1}
      >
        <Text color={theme.text.muted}>Loading suggestions...</Text>
      </PanelSection>
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
    <PanelSection
      paddingX={1}
      contentGap={0}
    >
      {/* Up scroll indicator */}
      {scrollOffset > 0 && <Text color={theme.text.primary}>▲</Text>}

      {/* Suggestions list */}
      {visibleSuggestions.map((suggestion, index) => {
        const originalIndex = startIndex + index;
        const isActive = originalIndex === activeIndex;
        const showCount = index === 0;
        const rowBackgroundColor = isActive ? colors.primary : undefined;
        const rowTextColor = isActive ? colors.bg : theme.text.secondary;
        const countColor = isActive ? rowTextColor : theme.text.muted;

        return (
          <Box
            key={`${suggestion.value}-${originalIndex}`}
            flexDirection="row"
            backgroundColor={rowBackgroundColor}
          >
            {/* Command name with slash */}
            <Box width={maxLabelWidth + 2} flexShrink={0}>
              <Text color={rowTextColor} bold={isActive}>
                /{suggestion.label}
              </Text>
            </Box>

            {/* Description */}
            {suggestion.description && (
              <Box flexGrow={1} paddingLeft={2}>
                <Text color={rowTextColor} wrap="truncate">
                  {suggestion.description}
                </Text>
              </Box>
            )}
            {!suggestion.description && <Box flexGrow={1} />}
            {showCount && (
              <Box flexShrink={0}>
                <Text color={countColor}>
                  ({activeIndex + 1}/{suggestions.length})
                </Text>
              </Box>
            )}
          </Box>
        );
      })}

      {/* Down scroll indicator */}
      {endIndex < suggestions.length && <Text color={theme.text.muted}>▼</Text>}
    </PanelSection>
  );
};
