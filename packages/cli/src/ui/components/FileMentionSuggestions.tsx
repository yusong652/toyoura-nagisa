/**
 * File Mention Suggestions Component
 *
 * Displays file suggestions dropdown for @ mention autocomplete.
 * Follows CLI bash-style design with keyboard navigation support.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';
import type { FileMentionSuggestion } from '../hooks/useFileMentionDetection.js';

// Maximum suggestions to show at once (must match hook constant)
const MAX_SUGGESTIONS_TO_SHOW = 8;

interface FileMentionSuggestionsProps {
  suggestions: FileMentionSuggestion[];
  selectedIndex: number;
  scrollOffset: number;
  isLoading: boolean;
}

export const FileMentionSuggestions: React.FC<FileMentionSuggestionsProps> = ({
  suggestions,
  selectedIndex,
  scrollOffset,
  isLoading,
}) => {
  // Calculate visible slice based on scrollOffset
  const startIndex = scrollOffset;
  const endIndex = Math.min(scrollOffset + MAX_SUGGESTIONS_TO_SHOW, suggestions.length);
  const visibleSuggestions = suggestions.slice(startIndex, endIndex);
  const showNoResults = suggestions.length === 0 && !isLoading;

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.default}
      paddingX={1}
    >
      {/* Header */}
      <Box>
        <Text color={theme.text.muted}>$ </Text>
        <Text color={theme.text.secondary}>files</Text>
        {!isLoading && suggestions.length > 0 && (
          <Text color={theme.text.muted}> ({selectedIndex + 1}/{suggestions.length})</Text>
        )}
      </Box>

      {/* Up scroll indicator */}
      {scrollOffset > 0 && <Text color={theme.text.primary}>▲</Text>}

      {/* Suggestions list */}
      {isLoading && suggestions.length === 0 ? (
        <Box>
          <Text color={theme.text.muted}>searching...</Text>
        </Box>
      ) : showNoResults ? (
        <Box>
          <Text color={theme.text.muted}>no results found</Text>
        </Box>
      ) : (
        visibleSuggestions.map((suggestion, index) => {
          const originalIndex = startIndex + index;
          const isSelected = originalIndex === selectedIndex;

          return (
            <Box key={suggestion.file.path}>
              <Text
                color={isSelected ? theme.text.accent : theme.text.muted}
                bold={isSelected}
              >
                {isSelected ? '> ' : '  '}
              </Text>
              <Text color={isSelected ? theme.text.primary : theme.text.secondary}>
                {suggestion.file.path}
              </Text>
            </Box>
          );
        })
      )}

      {/* Down scroll indicator */}
      {endIndex < suggestions.length && <Text color={theme.text.muted}>▼</Text>}

      {/* Footer hint */}
      <Box>
        <Text color={theme.text.muted}>
          {'\u2191\u2193'} navigate | {'\u23CE'} select | esc cancel
        </Text>
      </Box>
    </Box>
  );
};
