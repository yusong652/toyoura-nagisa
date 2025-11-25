/**
 * Input Prompt Component
 * Reference: Gemini CLI ui/components/InputPrompt.tsx (simplified)
 *
 * A multi-line input prompt for user messages with cursor navigation.
 * Uses TextBuffer with useReducer for reliable state management,
 * preventing issues with IME rapid character input.
 *
 * Supports:
 * - Left/Right arrow keys for cursor movement
 * - Up/Down arrow keys for line navigation
 * - Ctrl+A/Home for beginning of line
 * - Ctrl+E/End for end of line
 * - Backspace/Delete for character deletion
 * - Ctrl+U to clear line (to beginning)
 * - Ctrl+K to kill line (to end)
 * - Ctrl+W to delete word backward
 * - Ctrl+J for newline
 * - \ + Enter for newline (works in all terminals)
 * - Enter to submit
 */

import React, { useCallback, useRef } from 'react';
import { Box, Text } from 'ink';
import { useKeypress, type Key } from '../hooks/useKeypress.js';
import { useTextBuffer } from '../utils/text-buffer.js';
import { toCodePoints } from '../utils/textUtils.js';
import { theme } from '../colors.js';

interface InputPromptProps {
  onSubmit: (text: string) => void | Promise<void>;
  disabled?: boolean;
  placeholder?: string;
}

export const InputPrompt: React.FC<InputPromptProps> = ({
  onSubmit,
  disabled = false,
  placeholder = 'Type your message...',
}) => {
  const prefix = '> ';
  const continuationPrefix = '. ';
  const prefixWidth = prefix.length;

  // Track if last character was backslash (for \ + Enter newline)
  const lastKeyWasBackslash = useRef(false);

  // Use TextBuffer for reliable state management
  const buffer = useTextBuffer();

  // Handle submit
  const handleSubmit = useCallback(async () => {
    const fullText = buffer.text.trim();
    if (!fullText || disabled) return;

    await onSubmit(fullText);
    buffer.setText('');
    lastKeyWasBackslash.current = false;
  }, [buffer, disabled, onSubmit]);

  // Check if key matches newline command (Ctrl+J, or modifiers + Enter)
  const isNewlineKey = (key: Key): boolean => {
    // Return/Enter with modifiers (Ctrl, Shift, Meta/Cmd)
    if ((key.name === 'return' || key.name === 'enter') && (key.ctrl || key.shift || key.meta)) {
      return true;
    }
    // Ctrl+J sends '\n'
    if (key.sequence === '\n' || key.sequence === '\x0a') {
      return true;
    }
    return false;
  };

  // Handle backslash + Enter for newline
  const handleBackslashEnter = useCallback(() => {
    // Remove the trailing backslash and insert newline
    buffer.backspace();
    buffer.newline();
  }, [buffer]);

  const handleKeypress = useCallback(
    (key: Key) => {
      if (disabled) return;

      // Check for backslash + Enter (newline in all terminals)
      if (key.name === 'return' && lastKeyWasBackslash.current) {
        lastKeyWasBackslash.current = false;
        handleBackslashEnter();
        return;
      }

      // Track if this key is a backslash
      lastKeyWasBackslash.current = key.sequence === '\\';

      // Check for newline BEFORE checking for return/enter
      if (isNewlineKey(key)) {
        buffer.newline();
        return;
      }

      // Submit on Enter/Return (without modifiers)
      // Note: 'return' comes from '\r' (Enter key), 'enter' comes from '\n' (Ctrl+J)
      if (key.name === 'return' && !key.ctrl && !key.shift && !key.meta) {
        handleSubmit();
        return;
      }

      // Ctrl+C to clear input
      if (key.ctrl && key.name === 'c') {
        buffer.setText('');
        return;
      }

      // Delegate to buffer's handleInput for all other keys
      buffer.handleInput(key);
    },
    [disabled, buffer, handleSubmit, handleBackslashEnter]
  );

  useKeypress(handleKeypress, { isActive: !disabled });

  // Check if empty
  const isEmpty = buffer.lines.length === 1 && buffer.lines[0] === '';
  const [cursorRow, cursorCol] = buffer.cursor;

  // Render the input with cursor
  const renderLine = (line: string, lineIndex: number, isCurrentLine: boolean) => {
    const linePrefix = lineIndex === 0 ? prefix : continuationPrefix;
    const codePoints = toCodePoints(line);

    if (isEmpty && lineIndex === 0 && !disabled) {
      // Show placeholder with cursor at start
      return (
        <Box key={lineIndex} flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.accent}>{linePrefix}</Text>
          </Box>
          <Text inverse> </Text>
          <Text color={theme.text.muted} dimColor>{placeholder.slice(1)}</Text>
        </Box>
      );
    }

    if (!isCurrentLine) {
      // Non-active line - just render text
      return (
        <Box key={lineIndex} flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{linePrefix}</Text>
          </Box>
          <Text color={theme.text.primary}>{line}</Text>
        </Box>
      );
    }

    // Active line with cursor
    const beforeCursor = codePoints.slice(0, cursorCol).join('');
    const atCursor = codePoints[cursorCol] || ' ';
    const afterCursor = codePoints.slice(cursorCol + 1).join('');

    return (
      <Box key={lineIndex} flexDirection="row">
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={theme.text.accent}>{linePrefix}</Text>
        </Box>
        <Text color={theme.text.primary}>{beforeCursor}</Text>
        <Text inverse>{atCursor}</Text>
        <Text color={theme.text.primary}>{afterCursor}</Text>
      </Box>
    );
  };

  return (
    <Box flexDirection="column" marginTop={1}>
      {disabled ? (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{prefix}</Text>
          </Box>
          <Text color={theme.text.muted}>...</Text>
        </Box>
      ) : (
        buffer.lines.map((line, index) => renderLine(line, index, index === cursorRow))
      )}
    </Box>
  );
};
