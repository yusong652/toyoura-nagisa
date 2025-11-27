/**
 * History Item Display Component
 * Routes history items to appropriate message components
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { HistoryItem } from '../../types.js';
import { MessageType } from '../../types.js';
import { UserMessage } from './UserMessage.js';
import { AssistantMessage } from './AssistantMessage.js';
import { ToolCallMessage } from './ToolCallMessage.js';
import { ToolResultMessage } from './ToolResultMessage.js';
import { ThinkingMessage } from './ThinkingMessage.js';
import { InfoMessage } from './InfoMessage.js';
import { ErrorMessage } from './ErrorMessage.js';
import { theme } from '../../colors.js';
import { useTerminalSize } from '../../hooks/useTerminalSize.js';

interface HistoryItemDisplayProps {
  item: HistoryItem;
}

// Reserve space for scrollbar (VirtualizedList has paddingRight={1})
const SCROLLBAR_WIDTH = 1;

export const HistoryItemDisplay: React.FC<HistoryItemDisplayProps> = ({ item }) => {
  const { columns: rawTerminalWidth } = useTerminalSize();
  // Reduce width to prevent overlap with scrollbar
  const terminalWidth = rawTerminalWidth - SCROLLBAR_WIDTH;

  switch (item.type) {
    case MessageType.USER:
      return <UserMessage item={item} />;

    case MessageType.ASSISTANT:
      return <AssistantMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.TOOL_CALL:
      // Historical tool calls are completed, show success status
      return <ToolCallMessage item={item} isSuccess={true} terminalWidth={terminalWidth} />;

    case MessageType.TOOL_RESULT:
      return <ToolResultMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.THINKING:
      return <ThinkingMessage item={item} />;

    case MessageType.INFO:
      return <InfoMessage item={item} />;

    case MessageType.ERROR:
      return <ErrorMessage item={item} />;

    default:
      return (
        <Box marginBottom={1}>
          <Text color={theme.text.muted}>Unknown message type</Text>
        </Box>
      );
  }
};
