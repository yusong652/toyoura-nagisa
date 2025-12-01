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
import { getCachedStringWidth } from '../../utils/textUtils.js';

// Maximum lines for thinking blocks (shows last N lines when exceeded)
const MAX_THINKING_LINES = 3;

interface PendingItemDisplayProps {
  item: HistoryItemWithoutId;
}

/**
 * Get the last N lines of content, showing most recent thinking
 */
function getLastLines(content: string, maxLines: number): { text: string; truncated: boolean } {
  const lines = content.split('\n');
  if (lines.length <= maxLines) {
    return { text: content, truncated: false };
  }
  return {
    text: lines.slice(-maxLines).join('\n'),
    truncated: true,
  };
}

// Render content block for assistant message
const renderContentBlock = (block: ContentBlock, index: number, isStreaming: boolean): React.ReactNode => {
  switch (block.type) {
    case 'text': {
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayText = block.text.trim();
      return (
        <Box key={`text-${index}`} flexDirection="row">
          <Text wrap="wrap" color={theme.text.primary}>
            {displayText}
          </Text>
          {isStreaming && (
            <Text color={theme.text.muted}>▌</Text>
          )}
        </Box>
      );
    }

    case 'thinking': {
      // Trim and limit thinking content to last N lines (auto-scroll effect)
      const { text, truncated } = getLastLines(block.thinking.trim(), MAX_THINKING_LINES);
      return (
        <Box key={`thinking-${index}`} flexDirection="column">
          {truncated && (
            <Text color={theme.text.muted}>...</Text>
          )}
          <Text color={theme.message.thinking} dimColor wrap="wrap">
            {text}
          </Text>
        </Box>
      );
    }

    default:
      return null;
  }
};

// Pending Assistant Message
const PendingAssistantMessage: React.FC<{ item: AssistantHistoryItemWithoutId }> = ({ item }) => {
  // Use ⏺ (ball) prefix - represents Nagisa
  const prefix = '⏺ ';
  const prefixWidth = getCachedStringWidth(prefix);

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

// Status indicator width (matches ToolResultMessage)
const STATUS_INDICATOR_WIDTH = 3;
// Maximum lines for tool result content
const MAX_RESULT_LINES = 10;

// Pending Tool Result Message
// Layout matches ToolResultMessage for visual consistency
const PendingToolResultMessage: React.FC<{ item: ToolResultHistoryItemWithoutId }> = ({ item }) => {
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  const statusIcon = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;

  // Trim and split content into lines (matches ToolResultMessage behavior)
  const content = (item.content || '').trimEnd();
  const allLines = content.split('\n');
  const truncated = allLines.length > MAX_RESULT_LINES;
  const lines = truncated ? allLines.slice(0, MAX_RESULT_LINES) : allLines;

  return (
    <Box flexDirection="column" paddingX={1} marginBottom={1}>
      {/* Header line: status + tool name */}
      <Box>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusIcon}</Text>
        </Box>
        <Text color={theme.text.secondary}>
          {item.toolName || 'tool result'}
        </Text>
      </Box>
      {/* Content lines */}
      {lines.map((line, index) => (
        <Box key={index} paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text wrap="truncate-end" color={theme.text.secondary}>
            {line}
          </Text>
        </Box>
      ))}
      {truncated && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text color={theme.text.muted}>
            ... (output truncated)
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
