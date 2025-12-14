/**
 * Full Context View Component
 * Overlay that displays complete history with full thinking blocks and tool results
 *
 * Activated by Ctrl+O, provides a scrollable view of all context
 * Press ESC or Ctrl+O again to return to normal view
 *
 * Reuses the same message components as normal mode for consistent styling.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text } from 'ink';
import { useAppState } from '../contexts/AppStateContext.js';
import { theme } from '../colors.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { useKeypress, type Key } from '../hooks/useKeypress.js';
import { HistoryItemDisplay } from './messages/HistoryItemDisplay.js';

interface FullContextViewProps {
  onClose: () => void;
}

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

      {/* Content area - reuse same components as normal mode */}
      <Box flexDirection="column" flexGrow={1}>
        {history.length === 0 ? (
          <Text color={theme.text.muted}>No history to display.</Text>
        ) : (
          history.map((item) => (
            <HistoryItemDisplay key={item.id} item={item} />
          ))
        )}
      </Box>
    </Box>
  );
};
