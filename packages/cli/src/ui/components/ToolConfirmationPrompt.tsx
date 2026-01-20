/**
 * Tool Confirmation Prompt Component
 * Reference: Gemini CLI ui/components/messages/ToolConfirmationMessage.tsx
 *
 * Displays a confirmation prompt for tool execution with keyboard navigation.
 * Supports different confirmation types:
 * - edit: Shows git diff-style visualization for file changes
 * - exec: Shows command to be executed
 * - info: Generic tool confirmation
 *
 * Confirmation outcomes:
 * - approve: Execute the tool
 * - reject: Stop execution, user wants to provide input via main input
 * - reject_and_tell: Continue execution with user's brief instruction
 *
 * The third option "Reject and tell" has inline text input - user can type
 * directly when option 3 is selected without needing to "enter" input mode.
 */

import React, { useMemo, useState } from 'react';
import { Box, Text, useStdout } from 'ink';
import type {
  ToolConfirmationData,
  EditToolConfirmationData,
  ExecToolConfirmationData,
  InfoToolConfirmationData,
} from '../types.js';
import { theme, colors } from '../colors.js';
import { useKeypress } from '../hooks/useKeypress.js';
import { DiffRenderer, getDiffStats } from './DiffRenderer.js';
import { PanelSection } from './shared/PanelSection.js';

// Confirmation outcome types matching backend
export type ConfirmationOutcome = 'approve' | 'reject' | 'reject_and_tell';

interface ToolConfirmationPromptProps {
  data: ToolConfirmationData;
  onConfirm: (outcome: ConfirmationOutcome, message?: string) => void;
  isFocused?: boolean;
}

export const ToolConfirmationPrompt: React.FC<ToolConfirmationPromptProps> = ({
  data,
  onConfirm,
  isFocused = true,
}) => {
  const { stdout } = useStdout();
  const terminalWidth = stdout?.columns ?? 80;
  const terminalHeight = stdout?.rows ?? 24;

  // Active option index (0: approve, 1: reject, 2: reject_and_tell)
  const [activeIndex, setActiveIndex] = useState(0);
  // Input value for option 3 (reject_and_tell)
  const [inputValue, setInputValue] = useState('');
  // Cursor position for text input (state for rendering, ref for immediate access)
  const [cursorPosition, setCursorPosition] = useState(0);
  const cursorPositionRef = React.useRef(0);

  // Helper to update cursor position (both state and ref)
  const updateCursorPosition = React.useCallback((newPosition: number | ((prev: number) => number)) => {
    if (typeof newPosition === 'function') {
      setCursorPosition((prev) => {
        const next = newPosition(prev);
        cursorPositionRef.current = next;
        return next;
      });
    } else {
      cursorPositionRef.current = newPosition;
      setCursorPosition(newPosition);
    }
  }, []);

  // Cursor blink state
  const [cursorVisible, setCursorVisible] = useState(true);

  // Ensure cursor position stays within bounds
  React.useEffect(() => {
    if (cursorPosition > inputValue.length) {
      updateCursorPosition(inputValue.length);
    }
  }, [inputValue.length, cursorPosition, updateCursorPosition]);

  // Cursor blink effect for option 3
  React.useEffect(() => {
    if (!isFocused || activeIndex !== 2) return;

    const interval = setInterval(() => {
      setCursorVisible((v) => !v);
    }, 500);

    return () => clearInterval(interval);
  }, [isFocused, activeIndex]);

  // Calculate available height for diff content
  const UI_CHROME_HEIGHT = 14;

  const availableHeight = useMemo(() => {
    const confirmationType = (data as { type?: string }).type;
    if (confirmationType === 'edit') {
      return Math.max(3, terminalHeight - UI_CHROME_HEIGHT);
    }
    return 0;
  }, [data, terminalHeight]);

  // Unified keyboard handler using our custom useKeypress
  useKeypress(
    (key) => {
      if (!isFocused) return;

      // Escape or Ctrl+C to reject
      if (key.name === 'escape' || (key.ctrl && key.name === 'c')) {
        onConfirm('reject');
        return;
      }

      // Navigation: Up/Down arrows
      if (key.name === 'up') {
        setActiveIndex((prev) => Math.max(0, prev - 1));
        return;
      }
      if (key.name === 'down') {
        setActiveIndex((prev) => Math.min(2, prev + 1));
        return;
      }

      // Number keys for quick selection (disabled when typing in option 3)
      if (activeIndex !== 2) {
        if (key.name === '1') {
          setActiveIndex(0);
          return;
        }
        if (key.name === '2') {
          setActiveIndex(1);
          return;
        }
        if (key.name === '3') {
          setActiveIndex(2);
          return;
        }
      }

      // Enter to confirm
      if (key.name === 'return' || key.name === 'enter') {
        if (activeIndex === 0) {
          onConfirm('approve');
        } else if (activeIndex === 1) {
          onConfirm('reject');
        } else if (activeIndex === 2) {
          onConfirm('reject_and_tell', inputValue.trim() || undefined);
        }
        return;
      }

      // When on option 3, handle text input
      if (activeIndex === 2) {
        // Left arrow to move cursor left
        if (key.name === 'left') {
          updateCursorPosition((prev) => Math.max(0, prev - 1));
          return;
        }

        // Right arrow to move cursor right
        if (key.name === 'right') {
          updateCursorPosition((prev) => Math.min(inputValue.length, prev + 1));
          return;
        }

        // Home key to move cursor to start
        if (key.name === 'home' || (key.ctrl && key.name === 'a')) {
          updateCursorPosition(0);
          return;
        }

        // End key to move cursor to end
        if (key.name === 'end' || (key.ctrl && key.name === 'e')) {
          updateCursorPosition(inputValue.length);
          return;
        }

        // Backspace to delete character before cursor
        if (key.name === 'backspace') {
          const pos = cursorPositionRef.current;
          if (pos > 0) {
            setInputValue((prev) => prev.slice(0, pos - 1) + prev.slice(pos));
            updateCursorPosition(pos - 1);
          }
          return;
        }

        // Delete key to delete character at cursor
        if (key.name === 'delete') {
          const pos = cursorPositionRef.current;
          if (pos < inputValue.length) {
            setInputValue((prev) => prev.slice(0, pos) + prev.slice(pos + 1));
          }
          return;
        }

        // Ctrl+U to clear line
        if (key.ctrl && key.name === 'u') {
          setInputValue('');
          updateCursorPosition(0);
          return;
        }

        // Paste
        if (key.paste) {
          const pasteText = key.sequence;
          const pos = cursorPositionRef.current;
          setInputValue((prev) => prev.slice(0, pos) + pasteText + prev.slice(pos));
          updateCursorPosition(pos + pasteText.length);
          return;
        }

        // Printable characters - insert at cursor position
        // Use ref for immediate access to avoid stale closure issues with IME input
        if (key.insertable && key.sequence.length > 0) {
          const pos = cursorPositionRef.current;
          setInputValue((prev) => prev.slice(0, pos) + key.sequence + prev.slice(pos));
          updateCursorPosition(pos + key.sequence.length);
          return;
        }
      }
    },
    { isActive: isFocused }
  );

  // Render content based on confirmation type
  const { bodyContent, question } = useMemo(() => {
    let bodyContent: React.ReactNode = null;
    let question = 'Allow execution?';

    // Type guard to check confirmation type
    const confirmationType = (data as { type?: string }).type;

    if (confirmationType === 'edit') {
      const editData = data as EditToolConfirmationData;
      const diffStats = getDiffStats(editData.fileDiff);
      const isNewFile = editData.originalContent === '';

      question = 'Apply this change?';
      bodyContent = (
        <Box flexDirection="column">
          {/* File header with stats */}
          <Box flexDirection="row" gap={1}>
            <Text color={theme.text.link} bold>
              {editData.fileName}
            </Text>
            {isNewFile ? (
              <Text color={theme.status.success} dimColor>(new file)</Text>
            ) : (
              <>
                <Text color={theme.status.success}>+{diffStats.additions}</Text>
                <Text color={theme.status.error}>-{diffStats.deletions}</Text>
              </>
            )}
          </Box>

          {/* Diff content - clean, no extra border */}
          <Box marginTop={1} flexDirection="column">
            <DiffRenderer
              diffContent={editData.fileDiff}
              filename={editData.fileName}
              maxWidth={terminalWidth - 4}
              maxHeight={availableHeight}
            />
          </Box>
        </Box>
      );
    } else if (confirmationType === 'exec') {
      const execData = data as ExecToolConfirmationData;
      question = `Allow execution of: '${execData.rootCommand}'?`;
      bodyContent = (
        <PanelSection paddingX={1} backgroundColor={colors.bg}>
          <Text color={theme.text.link} wrap="wrap">
            {execData.command}
          </Text>
        </PanelSection>
      );
    } else if (confirmationType === 'info') {
      const infoData = data as InfoToolConfirmationData;
      question = 'Do you want to proceed?';
      bodyContent = (
        <Box flexDirection="column">
          <Box>
            <Text color={theme.text.muted}>Tool: </Text>
            <Text bold color={theme.text.primary}>
              {infoData.tool_name}
            </Text>
          </Box>
          {infoData.description && (
            <Box>
              <Text color={theme.text.muted}>Description: </Text>
              <Text color={theme.text.secondary}>{infoData.description}</Text>
            </Box>
          )}
          {infoData.command && (
            <Box marginTop={1}>
              <Text color={theme.text.secondary}>{infoData.command}</Text>
            </Box>
          )}
        </Box>
      );
    } else {
      // Legacy format without type field - use generic display
      bodyContent = (
        <Box flexDirection="column">
          <Box>
            <Text color={theme.text.muted}>Tool: </Text>
            <Text bold color={theme.text.primary}>
              {data.tool_name}
            </Text>
          </Box>
          {data.description && (
            <Box>
              <Text color={theme.text.muted}>Description: </Text>
              <Text color={theme.text.secondary}>{data.description}</Text>
            </Box>
          )}
          {(data as InfoToolConfirmationData).command && (
            <Box marginTop={1}>
              <Text color={theme.text.secondary}>
                {(data as InfoToolConfirmationData).command}
              </Text>
            </Box>
          )}
        </Box>
      );
    }

    return { bodyContent, question };
  }, [data, terminalWidth, availableHeight]);

  // Calculate maximum height for the entire component
  // This ensures the component never exceeds terminal height
  const maxComponentHeight = Math.max(UI_CHROME_HEIGHT, terminalHeight - 2);
  const activeBackground = colors.primary;
  const activeTextColor = colors.bg;
  const resolveTextColor = (isActive: boolean, fallback: string) =>
    isActive ? activeTextColor : fallback;
  const resolveBackgroundColor = (isActive: boolean) =>
    isActive ? activeBackground : undefined;

  return (
    <PanelSection
      title="Tool Confirmation"
      tone="accent"
      headerRight="esc"
      description={question}
      descriptionColor={theme.text.secondary}
      paddingX={1}
      maxHeight={maxComponentHeight}
      overflow="hidden"
      contentGap={1}
    >
      {/* Body Content (Diff or Command) - can shrink if needed */}
      <Box flexGrow={1} flexShrink={1} marginBottom={1} overflow="hidden">
        {bodyContent}
      </Box>

      {/* Custom options with inline input for option 3 */}
      <Box flexShrink={0} flexDirection="column">
        {/* Option 1: Yes, allow */}
        <Box backgroundColor={resolveBackgroundColor(activeIndex === 0)}>
          <Text color={resolveTextColor(activeIndex === 0, theme.text.primary)}>
            {activeIndex === 0 ? '● ' : '  '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 0, theme.text.muted)}>
            1.{' '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 0, theme.text.primary)}>
            Allow
          </Text>
        </Box>

        {/* Option 2: No, reject */}
        <Box backgroundColor={resolveBackgroundColor(activeIndex === 1)}>
          <Text color={resolveTextColor(activeIndex === 1, theme.text.primary)}>
            {activeIndex === 1 ? '● ' : '  '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 1, theme.text.muted)}>
            2.{' '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 1, theme.text.primary)}>
            Reject
          </Text>
        </Box>

        {/* Option 3: Reject and tell (with inline input) */}
        <Box backgroundColor={resolveBackgroundColor(activeIndex === 2)}>
          <Text color={resolveTextColor(activeIndex === 2, theme.text.primary)}>
            {activeIndex === 2 ? '● ' : '  '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 2, theme.text.muted)}>
            3.{' '}
          </Text>
          <Text color={resolveTextColor(activeIndex === 2, theme.text.primary)}>
            Reject + note:{' '}
          </Text>
          {/* Inline input area */}
          {activeIndex === 2 ? (
            <Text>
              <Text color={resolveTextColor(true, theme.text.primary)}>
                {inputValue.slice(0, cursorPosition)}
              </Text>
              <Text inverse={cursorVisible}>{cursorPosition < inputValue.length ? inputValue[cursorPosition] : ' '}</Text>
              <Text color={resolveTextColor(true, theme.text.primary)}>
                {inputValue.slice(cursorPosition + 1)}
              </Text>
              {!inputValue && (
                <Text color={resolveTextColor(true, theme.text.muted)}>type instruction...</Text>
              )}
            </Text>
          ) : (
            <Text color={resolveTextColor(false, theme.text.muted)}>
              {inputValue || 'type instruction...'}
            </Text>
          )}
        </Box>
      </Box>

      {/* Help text - fixed height, never shrinks */}
      <Box marginTop={1} flexShrink={0}>
        <Text color={theme.text.muted}>
          {activeIndex === 2
            ? '(Enter submit, Esc reject, ←→ move cursor, ↑↓ select)'
            : '(↑↓ select, Enter confirm, Esc reject)'}
        </Text>
      </Box>
    </PanelSection>
  );
};
