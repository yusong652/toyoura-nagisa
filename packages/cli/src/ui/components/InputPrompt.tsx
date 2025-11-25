/**
 * Input Prompt Component
 * Reference: Gemini CLI ui/components/InputPrompt.tsx (simplified)
 *
 * A simple input prompt for user messages.
 * Future enhancements: multiline, history navigation, slash command completion
 */

import React, { useState, useCallback } from 'react';
import { Box, Text, useInput } from 'ink';
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
  const [value, setValue] = useState('');
  const prefix = '> ';
  const prefixWidth = prefix.length;

  const handleSubmit = useCallback(async () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;

    await onSubmit(trimmed);
    setValue('');
  }, [value, disabled, onSubmit]);

  useInput(
    (input, key) => {
      if (disabled) return;

      if (key.return) {
        handleSubmit();
        return;
      }

      if (key.backspace || key.delete) {
        setValue((prev) => prev.slice(0, -1));
        return;
      }

      // Handle Ctrl+C to clear input
      if (input === '\x03') {
        setValue('');
        return;
      }

      // Handle Ctrl+U to clear line
      if (input === '\x15') {
        setValue('');
        return;
      }

      // Regular character input
      if (input && !key.ctrl && !key.meta) {
        setValue((prev) => prev + input);
      }
    },
    { isActive: !disabled },
  );

  const displayValue = value || (disabled ? '' : placeholder);
  const isPlaceholder = !value && !disabled;

  return (
    <Box flexDirection="row" marginTop={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={disabled ? theme.text.muted : theme.text.accent}>
          {prefix}
        </Text>
      </Box>
      <Box flexGrow={1}>
        <Text
          color={isPlaceholder ? theme.text.muted : theme.text.primary}
          dimColor={isPlaceholder}
        >
          {displayValue}
        </Text>
        {!disabled && !isPlaceholder && (
          <Text color={theme.text.accent}>_</Text>
        )}
      </Box>
    </Box>
  );
};
