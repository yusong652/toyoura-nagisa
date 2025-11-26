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

interface FileMentionSuggestionsProps {
  suggestions: FileMentionSuggestion[];
  selectedIndex: number;
  isLoading: boolean;
  maxDisplay?: number;
}

/**
 * Get file type indicator based on extension
 */
function getFileTypeIndicator(filename: string): string {
  const extension = filename.split('.').pop()?.toLowerCase();

  switch (extension) {
    case 'py':
      return 'py';
    case 'ts':
    case 'tsx':
      return 'ts';
    case 'js':
    case 'jsx':
      return 'js';
    case 'md':
      return 'md';
    case 'json':
      return 'json';
    case 'txt':
      return 'txt';
    case 'css':
    case 'scss':
      return 'css';
    case 'html':
      return 'html';
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
      return 'img';
    default:
      return 'file';
  }
}

export const FileMentionSuggestions: React.FC<FileMentionSuggestionsProps> = ({
  suggestions,
  selectedIndex,
  isLoading,
  maxDisplay = 8,
}) => {
  const displaySuggestions = suggestions.slice(0, maxDisplay);
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
        {!isLoading && (
          <Text color={theme.text.muted}> [{displaySuggestions.length}]</Text>
        )}
      </Box>

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
        displaySuggestions.map((suggestion, index) => {
          const isSelected = index === selectedIndex;
          const fileType = getFileTypeIndicator(suggestion.file.filename);

          return (
            <Box key={suggestion.file.path}>
              <Text
                color={isSelected ? theme.text.accent : theme.text.muted}
                bold={isSelected}
              >
                {isSelected ? '> ' : '  '}
              </Text>
              <Text color={theme.status.info}>[{fileType}]</Text>
              <Text color={isSelected ? theme.text.primary : theme.text.secondary}>
                {' '}
                {suggestion.file.path}
              </Text>
            </Box>
          );
        })
      )}

      {/* Footer hint */}
      <Box>
        <Text color={theme.text.muted}>
          {'\u2191\u2193'} navigate | {'\u23CE'} select | esc cancel
        </Text>
      </Box>
    </Box>
  );
};
