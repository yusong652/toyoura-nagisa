/**
 * Full Context View Component
 * Overlay that displays complete history with full thinking blocks and tool results
 *
 * Activated by Ctrl+O, provides a scrollable view of all context
 * Press ESC or Ctrl+O again to return to normal view
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text } from 'ink';
import { useAppState } from '../contexts/AppStateContext.js';
import { theme } from '../colors.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { useKeypress, type Key } from '../hooks/useKeypress.js';
import { MarkdownText } from './MarkdownText.js';
import type { HistoryItem, ContentBlock } from '../types.js';
import { MessageType } from '../types.js';

interface FullContextViewProps {
  onClose: () => void;
}

/**
 * Render a single history item with full content (no truncation)
 */
const FullHistoryItem: React.FC<{ item: HistoryItem }> = ({ item }) => {
  switch (item.type) {
    case MessageType.USER:
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color={theme.message.user}>User:</Text>
          <Box paddingLeft={2}>
            <MarkdownText>{item.text}</MarkdownText>
          </Box>
        </Box>
      );

    case MessageType.ASSISTANT:
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color={theme.text.accent}>Assistant:</Text>
          <Box paddingLeft={2} flexDirection="column">
            {item.content.map((block: ContentBlock, index: number) => {
              if (block.type === 'text') {
                return (
                  <Box key={`text-${index}`}>
                    <MarkdownText>{block.text.trim()}</MarkdownText>
                  </Box>
                );
              }
              if (block.type === 'thinking') {
                return (
                  <Box key={`thinking-${index}`} flexDirection="column" marginY={1}>
                    <Text bold color={theme.text.muted}>Thinking:</Text>
                    <Box paddingLeft={2}>
                      <MarkdownText dimColor baseColor={theme.message.thinking}>
                        {block.thinking.trim()}
                      </MarkdownText>
                    </Box>
                  </Box>
                );
              }
              return null;
            })}
          </Box>
        </Box>
      );

    case MessageType.TOOL_CALL:
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color={theme.message.tool}>Tool Call: {item.toolName}</Text>
          <Box paddingLeft={2}>
            <Text color={theme.text.secondary}>
              {JSON.stringify(item.toolInput, null, 2)}
            </Text>
          </Box>
        </Box>
      );

    case MessageType.TOOL_RESULT:
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color={item.isError ? theme.status.error : theme.status.success}>
            Tool Result {item.toolName ? `(${item.toolName})` : ''}:
          </Text>
          <Box paddingLeft={2}>
            <MarkdownText>{item.content}</MarkdownText>
          </Box>
        </Box>
      );

    case MessageType.INFO:
      return (
        <Box marginBottom={1}>
          <Text color={theme.status.info}>[info] {item.message}</Text>
        </Box>
      );

    case MessageType.ERROR:
      return (
        <Box marginBottom={1}>
          <Text color={theme.status.error}>[error] {item.message}</Text>
        </Box>
      );

    default:
      return null;
  }
};

export const FullContextView: React.FC<FullContextViewProps> = ({ onClose }) => {
  const appState = useAppState();
  const { rows: terminalHeight, columns: terminalWidth } = useTerminalSize();

  // Scroll position (line offset from top)
  const [scrollOffset, setScrollOffset] = useState(0);

  // Handle keyboard input
  const handleKeypress = useCallback((key: Key) => {
    // Close on ESC or Ctrl+O
    if (key.name === 'escape' || (key.ctrl && key.name === 'o')) {
      onClose();
      return;
    }

    // Scroll up/down
    if (key.name === 'up' || key.name === 'k') {
      setScrollOffset(prev => Math.max(0, prev - 1));
    }
    if (key.name === 'down' || key.name === 'j') {
      setScrollOffset(prev => prev + 1);
    }

    // Page up/down
    if (key.name === 'pageup') {
      setScrollOffset(prev => Math.max(0, prev - (terminalHeight - 4)));
    }
    if (key.name === 'pagedown') {
      setScrollOffset(prev => prev + (terminalHeight - 4));
    }

    // Home/End (g/G for vim-style)
    if (key.name === 'home' || key.name === 'g') {
      setScrollOffset(0);
    }
    if (key.name === 'end' || key.name === 'G') {
      // Scroll to bottom (will be clamped by render)
      setScrollOffset(Infinity);
    }
  }, [onClose, terminalHeight]);

  useKeypress(handleKeypress, { isActive: true });

  // Reset scroll when history changes
  useEffect(() => {
    setScrollOffset(0);
  }, [appState.history.length]);

  const history = appState.history;

  return (
    <Box flexDirection="column" width={terminalWidth}>
      {/* Header - minimal */}
      <Box paddingX={1} marginBottom={1}>
        <Text bold color={theme.status.info}>Full Context</Text>
        <Text color={theme.text.muted}> | </Text>
        <Text color={theme.text.secondary}>
          {history.length} items | ESC/Ctrl+O close
        </Text>
      </Box>

      {/* Content area */}
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        {history.length === 0 ? (
          <Text color={theme.text.muted}>No history to display.</Text>
        ) : (
          history.map((item) => (
            <FullHistoryItem key={item.id} item={item} />
          ))
        )}
      </Box>
    </Box>
  );
};
