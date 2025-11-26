/**
 * Pending Item Display Component
 * Renders pending history items (items being streamed)
 *
 * Similar to HistoryItemDisplay but accepts HistoryItemWithoutId
 * (no id/timestamp required since these items haven't been committed yet)
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import {
  MessageType,
  type HistoryItemWithoutId,
  type AssistantHistoryItemWithoutId,
  type ToolCallHistoryItemWithoutId,
  type ToolResultHistoryItemWithoutId,
  type ErrorHistoryItemWithoutId,
  type ContentBlock,
} from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';
import { BlinkingCircle } from '../BlinkingCircle.js';

interface PendingItemDisplayProps {
  item: HistoryItemWithoutId;
}

// Render content block for assistant message
const renderContentBlock = (block: ContentBlock, index: number, isStreaming: boolean): React.ReactNode => {
  switch (block.type) {
    case 'text':
      return (
        <Box key={index} flexDirection="row">
          <Text wrap="wrap" color={theme.text.primary}>
            {block.text}
          </Text>
          {isStreaming && (
            <Text color={theme.text.muted}>▌</Text>
          )}
        </Box>
      );

    case 'thinking':
      return (
        <Box key={index} marginBottom={1}>
          <Text color={theme.message.thinking} dimColor wrap="wrap">
            {block.thinking}
          </Text>
        </Box>
      );

    default:
      return null;
  }
};

// Pending Assistant Message
const PendingAssistantMessage: React.FC<{ item: AssistantHistoryItemWithoutId }> = ({ item }) => {
  const prefix = '✦ ';
  const prefixWidth = 2;

  const content = item.content || [];
  const textBlocks = content.filter((b): b is ContentBlock & { type: 'text' } => b.type === 'text');
  const hasTextContent = textBlocks.length > 0 && textBlocks.some(b => b.text.length > 0);

  // Find last text block index
  let lastTextBlockIndex = -1;
  for (let i = content.length - 1; i >= 0; i--) {
    if (content[i].type === 'text') {
      lastTextBlockIndex = i;
      break;
    }
  }

  const isStreaming = item.isStreaming === true;

  return (
    <Box flexDirection="row" marginBottom={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.text.accent}>{prefix}</Text>
      </Box>
      <Box flexGrow={1} flexDirection="column">
        {content.map((block, index) => {
          const isLastTextBlock = block.type === 'text' && index === lastTextBlockIndex;
          return renderContentBlock(block, index, isStreaming && isLastTextBlock);
        })}
        {isStreaming && !hasTextContent && (
          <Text color={theme.ui.spinner}>
            <Spinner type="dots" />
          </Text>
        )}
      </Box>
    </Box>
  );
};

// Pending Tool Call Message
const PendingToolCallMessage: React.FC<{ item: ToolCallHistoryItemWithoutId }> = ({ item }) => {
  return (
    <Box marginBottom={1} flexDirection="row">
      <BlinkingCircle color={theme.status.warning} />
      <Text color={theme.text.secondary}>
        {' '}{item.toolName}
      </Text>
    </Box>
  );
};

// Pending Tool Result Message
const PendingToolResultMessage: React.FC<{ item: ToolResultHistoryItemWithoutId }> = ({ item }) => {
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  const statusIcon = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;

  // Truncate content for display
  const content = item.content || '';
  const truncatedContent = content.length > 200 ? content.substring(0, 200) + '...' : content;

  return (
    <Box marginBottom={1} flexDirection="column">
      <Box flexDirection="row">
        <Text color={statusColor}>{statusIcon} </Text>
        <Text color={theme.text.muted}>Tool result</Text>
      </Box>
      {truncatedContent && (
        <Box marginLeft={2}>
          <Text color={theme.text.muted} wrap="truncate-end">
            {truncatedContent}
          </Text>
        </Box>
      )}
    </Box>
  );
};

// Pending Error Message
const PendingErrorMessage: React.FC<{ item: ErrorHistoryItemWithoutId }> = ({ item }) => {
  return (
    <Box marginBottom={1}>
      <Text color={theme.status.error}>Error: {item.message}</Text>
    </Box>
  );
};

export const PendingItemDisplay: React.FC<PendingItemDisplayProps> = ({ item }) => {
  switch (item.type) {
    case MessageType.ASSISTANT:
      return <PendingAssistantMessage item={item} />;

    case MessageType.TOOL_CALL:
      return <PendingToolCallMessage item={item} />;

    case MessageType.TOOL_RESULT:
      return <PendingToolResultMessage item={item} />;

    case MessageType.ERROR:
      return <PendingErrorMessage item={item} />;

    default:
      return (
        <Box marginBottom={1}>
          <Text color={theme.text.muted}>Pending: {(item as any).type}</Text>
        </Box>
      );
  }
};
