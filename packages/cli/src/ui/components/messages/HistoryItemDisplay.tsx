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
import { InfoMessage } from './InfoMessage.js';
import { ErrorMessage } from './ErrorMessage.js';
import { ShellCommandMessage } from './ShellCommandMessage.js';
import { ShellResultMessage } from './ShellResultMessage.js';
import { PfcConsoleCommandMessage } from './PfcConsoleCommandMessage.js';
import { PfcConsoleResultMessage } from './PfcConsoleResultMessage.js';
import { theme } from '../../colors.js';
import { useTerminalSize } from '../../hooks/useTerminalSize.js';

interface HistoryItemDisplayProps {
  item: HistoryItem;
}

// Small padding to prevent content from touching the edge
const EDGE_PADDING = 1;

export const HistoryItemDisplay: React.FC<HistoryItemDisplayProps> = ({ item }) => {
  const { columns: rawTerminalWidth } = useTerminalSize();
  const terminalWidth = rawTerminalWidth - EDGE_PADDING;

  switch (item.type) {
    case MessageType.USER:
      return <UserMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.ASSISTANT:
      return <AssistantMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.TOOL_CALL:
      // Historical tool calls are completed
      return <ToolCallMessage item={item} isCompleted={true} terminalWidth={terminalWidth} />;

    case MessageType.TOOL_RESULT:
      return <ToolResultMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.INFO:
      return <InfoMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.ERROR:
      return <ErrorMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.SHELL_COMMAND:
      return <ShellCommandMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.SHELL_RESULT:
      return <ShellResultMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.PFC_CONSOLE_COMMAND:
      return <PfcConsoleCommandMessage item={item} terminalWidth={terminalWidth} />;

    case MessageType.PFC_CONSOLE_RESULT:
      return <PfcConsoleResultMessage item={item} terminalWidth={terminalWidth} />;

    default:
      return (
        <Box marginBottom={1}>
          <Text color={theme.text.muted}>Unknown message type</Text>
        </Box>
      );
  }
};
