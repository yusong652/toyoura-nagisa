/**
 * Input Prompt Component
 * Reference: Gemini CLI ui/components/InputPrompt.tsx (simplified)
 *
 * A multi-line input prompt for user messages with cursor navigation.
 * Uses TextBuffer with useReducer for reliable state management,
 * preventing issues with IME rapid character input.
 *
 * IMPORTANT: The buffer is passed as a prop from the parent component
 * to preserve state when dialogs are opened (component unmounts/remounts).
 *
 * Supports:
 * - Left/Right arrow keys for cursor movement
 * - Up/Down arrow keys for line navigation (or suggestion navigation)
 * - Ctrl+A/Home for beginning of line
 * - Ctrl+E/End for end of line
 * - Backspace/Delete for character deletion
 * - Ctrl+U to delete to beginning of line
 * - Ctrl+K to delete to end of line
 * - Ctrl+W to delete word backward
 * - Ctrl+J for newline
 * - \ + Enter for newline (works in all terminals)
 * - Tab to accept suggestion
 * - Enter to submit
 * - Slash commands with autocomplete (/)
 */

import React, { useCallback, useRef, useEffect, useMemo } from 'react';
import { Box, Text } from 'ink';
import { replaceMention } from '@toyoura-nagisa/core/utils';
import { useKeypress, type Key } from '../hooks/useKeypress.js';
import { useSlashCompletion } from '../hooks/useSlashCompletion.js';
import { useFileMentionDetection } from '../hooks/useFileMentionDetection.js';
import { toCodePoints } from '../utils/textUtils.js';
import { theme } from '../colors.js';
import { SlashCommandSuggestions } from './SlashCommandSuggestions.js';
import { FileMentionSuggestions } from './FileMentionSuggestions.js';
import type { SlashCommand, CommandContext } from '../commands/types.js';
import type { TextBuffer } from '../utils/text-buffer.js';

interface InputPromptProps {
  /** Text buffer for input state - managed by parent to survive unmount */
  buffer: TextBuffer;
  onSubmit: (text: string, mentionedFiles?: string[]) => void | Promise<void>;
  onSlashCommand?: (command: string, args: string) => void | Promise<void>;
  /** Callback for shell commands (! prefix) */
  onShellCommand?: (command: string) => void | Promise<void>;
  /** Callback when shell mode changes */
  onShellModeChange?: (isShellMode: boolean) => void;
  /** Callback when shell command is blocked during streaming */
  onShellBlocked?: () => void;
  /** Callback for PFC console commands (> prefix) */
  onPfcConsoleCommand?: (code: string) => void | Promise<void>;
  /** Callback when PFC console mode changes */
  onPfcConsoleModeChange?: (isPfcConsoleMode: boolean) => void;
  /** Callback when PFC console command is blocked during streaming */
  onPfcConsoleBlocked?: () => void;
  slashCommands?: readonly SlashCommand[];
  commandContext?: CommandContext;
  disabled?: boolean;
  /** Whether LLM is currently streaming (blocks shell/PFC commands) */
  isStreaming?: boolean;
  placeholder?: string;
  /** Agent profile for file search */
  agentProfile?: string;
  /** Session ID for file search */
  sessionId?: string;
}

export const InputPrompt: React.FC<InputPromptProps> = ({
  buffer,
  onSubmit,
  onSlashCommand,
  onShellCommand,
  onShellModeChange,
  onShellBlocked,
  onPfcConsoleCommand,
  onPfcConsoleModeChange,
  onPfcConsoleBlocked,
  slashCommands = [],
  commandContext,
  disabled = false,
  isStreaming = false,
  placeholder = 'Type your message...',
  agentProfile = 'general',
  sessionId,
}) => {
  // Default prefix width (all prefixes should have same width for alignment)
  const prefixWidth = 2;

  // Track if last character was backslash (for \ + Enter newline)
  const lastKeyWasBackslash = useRef(false);

  // Track mentioned files
  const mentionedFilesRef = useRef<string[]>([]);

  // Slash command completion
  const completion = useSlashCompletion({
    input: buffer.text,
    commands: slashCommands,
    commandContext,
    enabled: !disabled && slashCommands.length > 0,
  });

  // File mention detection
  const fileMention = useFileMentionDetection(
    buffer.text,
    buffer.absoluteCursor,
    agentProfile,
    sessionId
  );

  // Detect shell mode (input starts with !)
  const isInShellMode = useMemo(() => {
    const trimmed = buffer.text.trim();
    return trimmed.startsWith('!') && trimmed.length >= 1;
  }, [buffer.text]);

  // Detect PFC console mode (input starts with > but not >> for redirect)
  const isInPfcConsoleMode = useMemo(() => {
    const trimmed = buffer.text.trim();
    // > but not >> (shell redirect) and not > (empty)
    return trimmed.startsWith('>') && !trimmed.startsWith('>>') && trimmed.length >= 1;
  }, [buffer.text]);

  // Dynamic prefix based on mode (all 2 chars wide)
  const prefix = useMemo(() => {
    if (isInShellMode) return '! ';       // Shell mode: ! prefix (yellow)
    if (isInPfcConsoleMode) return '> ';  // PFC console mode: > prefix (blue)
    return '> ';                          // Default: > prefix (accent)
  }, [isInShellMode, isInPfcConsoleMode]);

  const continuationPrefix = '  ';  // Continuation lines (same width as prefix)

  // Notify parent when shell mode changes
  useEffect(() => {
    onShellModeChange?.(isInShellMode);
  }, [isInShellMode, onShellModeChange]);

  // Notify parent when PFC console mode changes
  useEffect(() => {
    onPfcConsoleModeChange?.(isInPfcConsoleMode);
  }, [isInPfcConsoleMode, onPfcConsoleModeChange]);

  // Check if input is a slash command
  const isSlashCommand = (text: string): boolean => {
    const trimmed = text.trim();
    return trimmed.startsWith('/') && !trimmed.startsWith('//') && !trimmed.startsWith('/*');
  };

  // Check if input is a shell command (! prefix)
  const isShellCommand = (text: string): boolean => {
    const trimmed = text.trim();
    return trimmed.startsWith('!') && trimmed.length > 1;
  };

  // Parse shell command from input (remove ! prefix)
  const parseShellCommand = (text: string): string => {
    return text.trim().substring(1);
  };

  // Check if input is a PFC console command (> prefix, not >>)
  const isPfcConsoleCommand = (text: string): boolean => {
    const trimmed = text.trim();
    return trimmed.startsWith('>') && !trimmed.startsWith('>>') && trimmed.length >= 1;
  };

  // Parse PFC console command from input (remove > prefix)
  const parsePfcConsoleCommand = (text: string): string => {
    return text.trim().substring(1).trim();
  };

  // Parse slash command from input
  const parseSlashCommand = (text: string): { name: string; args: string } | null => {
    const trimmed = text.trim();
    if (!isSlashCommand(trimmed)) return null;

    const content = trimmed.substring(1); // Remove "/"
    const spaceIndex = content.indexOf(' ');
    if (spaceIndex === -1) {
      return { name: content, args: '' };
    }
    return {
      name: content.substring(0, spaceIndex),
      args: content.substring(spaceIndex + 1).trim(),
    };
  };

  // Handle file mention selection
  const handleFileMentionSelect = useCallback(() => {
    const suggestion = fileMention.getSelectedSuggestion();
    if (!suggestion) return;

    const { atPosition } = fileMention.context;
    if (atPosition === -1) return;

    // Replace the mention query with the selected file path
    const { text: newText, cursor: newCursor } = replaceMention(
      buffer.text,
      atPosition,
      buffer.absoluteCursor,
      suggestion.file.path
    );

    // Add space after the file path
    const finalText = newText.slice(0, newCursor) + ' ' + newText.slice(newCursor);
    buffer.setText(finalText);
    buffer.setCursorToAbsolute(newCursor + 1);

    // Track the mentioned file
    if (!mentionedFilesRef.current.includes(suggestion.file.path)) {
      mentionedFilesRef.current.push(suggestion.file.path);
    }

    fileMention.clearMention();
  }, [buffer, fileMention]);

  // Handle submit and clear
  // Clear buffer BEFORE calling handlers to prevent re-submission issues
  const handleSubmitAndClear = useCallback(
    (submittedValue: string) => {
      // Block shell commands during LLM streaming to prevent file system inconsistency
      // Don't clear buffer so user can retry after streaming completes
      if (isShellCommand(submittedValue) && isStreaming) {
        onShellBlocked?.();
        return;
      }

      // Block PFC console commands during LLM streaming
      if (isPfcConsoleCommand(submittedValue) && isStreaming) {
        onPfcConsoleBlocked?.();
        return;
      }

      // Capture mentioned files before clearing
      const mentionedFiles = [...mentionedFilesRef.current];

      buffer.setText('');
      completion.reset();
      fileMention.clearMention();
      mentionedFilesRef.current = [];
      lastKeyWasBackslash.current = false;

      // Check for shell command (! prefix) - takes precedence
      if (isShellCommand(submittedValue) && onShellCommand) {
        const shellCommand = parseShellCommand(submittedValue);
        onShellCommand(shellCommand);
        return;
      }

      // Check for PFC console command (> prefix)
      if (isPfcConsoleCommand(submittedValue) && onPfcConsoleCommand) {
        const pfcCode = parsePfcConsoleCommand(submittedValue);
        onPfcConsoleCommand(pfcCode);
        return;
      }

      // Check for slash command
      if (isSlashCommand(submittedValue) && onSlashCommand) {
        const parsed = parseSlashCommand(submittedValue);
        if (parsed) {
          onSlashCommand(parsed.name, parsed.args);
          return;
        }
      }

      onSubmit(submittedValue, mentionedFiles.length > 0 ? mentionedFiles : undefined);
    },
    [buffer, completion, fileMention, onSubmit, onSlashCommand, onShellCommand, onPfcConsoleCommand, isStreaming, onShellBlocked, onPfcConsoleBlocked]
  );

  // Handle submit
  const handleSubmit = useCallback(() => {
    const fullText = buffer.text.trim();
    if (!fullText || disabled) return;
    handleSubmitAndClear(fullText);
  }, [buffer, disabled, handleSubmitAndClear]);

  // Handle autocomplete selection
  const handleAutocomplete = useCallback(() => {
    const selectedValue = completion.getSelectedValue();
    if (!selectedValue) return;

    const { start, end } = completion.completionRange;
    const text = buffer.text;

    // Build new text with the selected value
    let newText: string;
    if (start === 0 && end === text.length) {
      // Replace entire command
      newText = '/' + selectedValue + ' ';
    } else if (start === end) {
      // Insert at position
      newText = text.slice(0, start) + selectedValue + ' ' + text.slice(end);
    } else {
      // Replace range
      const prefixText = text.slice(0, start);
      const suffix = text.slice(end);
      newText = prefixText + selectedValue + ' ' + suffix;
    }

    buffer.setText(newText);
  }, [buffer, completion]);

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

  // Handle autocomplete and execute: select suggestion and immediately submit
  const handleAutocompleteAndExecute = useCallback(() => {
    const selectedValue = completion.getSelectedValue();
    if (!selectedValue) return;

    // Build command text with the selected value
    const commandText = '/' + selectedValue;

    // Submit the command directly
    handleSubmitAndClear(commandText);
  }, [completion, handleSubmitAndClear]);

  const handleKeypress = useCallback(
    (key: Key) => {
      if (disabled) return;

      // Handle file mention navigation when file suggestions are visible
      if (fileMention.isMentionActive) {
        // Up arrow - navigate file suggestions
        if (key.name === 'up') {
          fileMention.selectPrevious();
          return;
        }
        // Down arrow - navigate file suggestions
        if (key.name === 'down') {
          fileMention.selectNext();
          return;
        }
        // Tab or Enter - select file suggestion
        if (key.name === 'tab' || (key.name === 'return' && !key.ctrl && !key.shift && !key.meta)) {
          handleFileMentionSelect();
          return;
        }
        // Escape - dismiss file suggestions
        if (key.name === 'escape') {
          fileMention.clearMention();
          return;
        }
      }

      // Handle slash command suggestion navigation when suggestions are visible
      if (completion.showSuggestions) {
        // Up arrow - navigate suggestions
        if (key.name === 'up') {
          completion.navigateUp();
          return;
        }
        // Down arrow - navigate suggestions
        if (key.name === 'down') {
          completion.navigateDown();
          return;
        }
        // Tab - accept suggestion (autocomplete only, don't execute)
        if (key.name === 'tab') {
          handleAutocomplete();
          return;
        }
        // Enter - accept suggestion and execute command
        if (key.name === 'return' && !key.ctrl && !key.shift && !key.meta) {
          handleAutocompleteAndExecute();
          return;
        }
        // Escape - hide suggestions (reset)
        if (key.name === 'escape') {
          completion.reset();
          return;
        }
      }

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

      // Delegate to buffer's handleInput for all other keys
      // Note: Ctrl+C is handled at app level for quit/interrupt
      buffer.handleInput(key);
    },
    [disabled, buffer, handleSubmit, handleBackslashEnter, completion, handleAutocomplete, handleAutocompleteAndExecute, fileMention, handleFileMentionSelect]
  );

  useKeypress(handleKeypress, { isActive: !disabled });

  // Check if empty
  const isEmpty = buffer.lines.length === 1 && buffer.lines[0] === '';

  // Use visual cursor for correct cursor positioning in wrapped lines
  const [visualCursorRow, visualCursorCol] = buffer.visualCursor;

  // Prefix color based on mode
  const prefixColor = useMemo(() => {
    if (isInShellMode) return theme.status.warning;      // Shell mode: yellow
    if (isInPfcConsoleMode) return theme.status.info;    // PFC console mode: blue
    return theme.text.accent;                            // Default
  }, [isInShellMode, isInPfcConsoleMode]);

  // Render a visual line with cursor
  const renderVisualLine = (
    visualLine: string,
    visualLineIndex: number,
    isCurrentLine: boolean
  ) => {
    // Only show prefix on the very first line
    const isFirstLine = visualLineIndex === 0;
    const linePrefix = isFirstLine ? prefix : continuationPrefix;

    // Hide trigger character on first line in special modes
    const shouldHideTrigger = isFirstLine && (isInShellMode || isInPfcConsoleMode);
    const displayLine = shouldHideTrigger ? visualLine.slice(1) : visualLine;
    const codePoints = toCodePoints(displayLine);

    // Adjust cursor position if trigger is hidden
    const adjustedCursorCol = shouldHideTrigger && isCurrentLine
      ? Math.max(0, visualCursorCol - 1)
      : visualCursorCol;

    if (isEmpty && visualLineIndex === 0 && !disabled) {
      // Show placeholder with cursor at start
      return (
        <Box key={visualLineIndex} flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={prefixColor}>{linePrefix}</Text>
          </Box>
          <Text inverse> </Text>
          <Text color={theme.text.muted} dimColor>{placeholder.slice(1)}</Text>
        </Box>
      );
    }

    if (!isCurrentLine) {
      // Non-active line - just render text
      return (
        <Box key={visualLineIndex} flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={isFirstLine ? prefixColor : theme.text.muted}>
              {linePrefix}
            </Text>
          </Box>
          <Text color={theme.text.primary}>{displayLine}</Text>
        </Box>
      );
    }

    // Active line with cursor
    const beforeCursor = codePoints.slice(0, adjustedCursorCol).join('');
    const atCursor = codePoints[adjustedCursorCol] || ' ';
    const afterCursor = codePoints.slice(adjustedCursorCol + 1).join('');

    return (
      <Box key={visualLineIndex} flexDirection="row">
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={isFirstLine ? prefixColor : theme.text.muted}>
            {linePrefix}
          </Text>
        </Box>
        <Text color={theme.text.primary}>{beforeCursor}</Text>
        <Text inverse>{atCursor}</Text>
        <Text color={theme.text.primary}>{afterCursor}</Text>
      </Box>
    );
  };

  // Determine border color based on state
  const borderColor = disabled
    ? theme.border.default
    : isInShellMode
      ? theme.status.warning
      : isInPfcConsoleMode
        ? theme.status.info
        : theme.border.focused;

  return (
    <Box flexDirection="column">
      {/* Input box */}
      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor={borderColor}
        paddingX={1}
      >
        {disabled ? (
          <Box flexDirection="row">
            <Box width={prefixWidth} flexShrink={0}>
              <Text color={theme.text.muted}>{prefix}</Text>
            </Box>
            <Text color={theme.text.muted}>...</Text>
          </Box>
        ) : (
          buffer.visualLines.map((visualLine, index) =>
            renderVisualLine(visualLine, index, index === visualCursorRow)
          )
        )}
      </Box>

      {/* File mention suggestions popup (below input) */}
      {fileMention.isMentionActive && (
        <FileMentionSuggestions
          suggestions={fileMention.suggestions}
          selectedIndex={fileMention.selectedIndex}
          scrollOffset={fileMention.scrollOffset}
          isLoading={fileMention.isSearching}
        />
      )}

      {/* Slash command suggestions popup (below input) */}
      {completion.showSuggestions && !fileMention.isMentionActive && (
        <SlashCommandSuggestions
          suggestions={completion.suggestions}
          activeIndex={completion.activeIndex}
          isLoading={completion.isLoading}
          scrollOffset={completion.scrollOffset}
        />
      )}
    </Box>
  );
};
