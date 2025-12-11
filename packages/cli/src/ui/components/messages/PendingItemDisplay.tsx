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
// Keep in sync with AssistantMessage.tsx for consistent display
const MAX_THINKING_LINES = 4;

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

// Status indicator width (matches ToolCallMessage and ToolResultMessage)
const STATUS_INDICATOR_WIDTH = 3;
// Maximum lines for tool result content
const MAX_RESULT_LINES = 10;
// Maximum SubAgent tools to show (shows most recent, older ones collapsed)
const MAX_SUBAGENT_TOOLS_SHOWN = 5;

/**
 * Get tool description from input parameters
 * (matches ToolCallMessage logic)
 */
function getToolDescription(toolName: string, input: Record<string, unknown>): string {
  // For edit/write tools, show file name
  if (toolName === 'edit' || toolName === 'write') {
    if (input.file_path !== undefined) {
      const filePath = String(input.file_path);
      const parts = filePath.split(/[/\\]/);
      return parts[parts.length - 1] || filePath;
    }
  }

  // Common tool input patterns
  if (input.command !== undefined) return String(input.command);
  if (input.file_path !== undefined) return String(input.file_path);
  if (input.path !== undefined) return String(input.path);
  if (input.pattern !== undefined) return String(input.pattern);
  if (input.query !== undefined) return String(input.query);
  if (input.url !== undefined) return String(input.url);

  // For other tools, show a summary of the input
  const keys = Object.keys(input);
  if (keys.length > 0) {
    const firstKey = keys[0];
    const value = input[firstKey];
    if (typeof value === 'string' && value.length < 100) {
      return value;
    }
    return `${firstKey}: ...`;
  }
  return '';
}

// SubAgent Tool Item (nested under invoke_agent)
// Displayed with additional indentation and dimmer styling
// Shows BlinkingCircle when executing, checkmark/error when tool completes
const SubagentToolItemDisplay: React.FC<{
  toolName: string;
  toolInput: Record<string, unknown>;
  hasResult?: boolean;   // True when this specific tool completed
  isError?: boolean;     // True if tool execution resulted in error
  parentCompleted: boolean;  // Fallback: when invoke_agent has result, all SubAgent tools are done
}> = ({ toolName, toolInput, hasResult, isError, parentCompleted }) => {
  const description = getToolDescription(toolName, toolInput);
  // Additional indent for nested tools (2 spaces)
  const SUBAGENT_INDENT = 2;

  // Tool is completed if it has its own result, or if parent (invoke_agent) is completed
  const isCompleted = hasResult === true || parentCompleted;
  const statusIcon = isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = isError ? theme.status.error : theme.text.muted;

  return (
    <Box paddingX={1} paddingLeft={STATUS_INDICATOR_WIDTH + SUBAGENT_INDENT}>
      <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
        {isCompleted ? (
          <Text color={statusColor}>{statusIcon}</Text>
        ) : (
          <BlinkingCircle color={theme.text.muted} />
        )}
      </Box>
      <Text wrap="truncate" dimColor>
        <Text bold color={theme.text.muted}>
          {toolName}
        </Text>
        {description && (
          <Text color={theme.text.muted}> {description}</Text>
        )}
      </Text>
    </Box>
  );
};

// Pending Tool Call Message
// Layout matches ToolCallMessage for visual consistency
// Shows BlinkingCircle when executing, success/error icon when result received
const PendingToolCallMessage: React.FC<{ item: ToolCallHistoryItemWithoutId }> = ({ item }) => {
  const hasResult = item.hasResult === true;
  const isError = item.isError === true;
  const subagentTools = item.subagentTools || [];

  // Check if this is an invoke_agent call
  const isInvokeAgent = item.toolName === 'invoke_agent';
  const subagentType = isInvokeAgent ? String(item.toolInput.subagent_type || 'SubAgent') : '';

  // For invoke_agent: show description (task summary), otherwise use standard description
  const description = isInvokeAgent
    ? String(item.toolInput.description || '')
    : getToolDescription(item.toolName, item.toolInput);

  // Color based on result status: success (green) or error (red)
  const statusColor = isError ? theme.status.error : theme.status.success;
  const statusIcon = isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;

  // Limit SubAgent tools displayed (show most recent, collapse older ones)
  const totalSubagentTools = subagentTools.length;
  const hiddenCount = Math.max(0, totalSubagentTools - MAX_SUBAGENT_TOOLS_SHOWN);
  const visibleSubagentTools = hiddenCount > 0
    ? subagentTools.slice(-MAX_SUBAGENT_TOOLS_SHOWN)
    : subagentTools;

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box paddingX={1}>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          {hasResult ? (
            <Text color={statusColor}>{statusIcon}</Text>
          ) : (
            <BlinkingCircle color={theme.status.success} />
          )}
        </Box>
        {isInvokeAgent ? (
          // Special display for invoke_agent: show SubAgent type with accent background
          <Text wrap="truncate">
            <Text bold color={theme.text.accent} inverse>
              {subagentType}
            </Text>
            {description && (
              <Text color={theme.text.secondary}> {description}</Text>
            )}
          </Text>
        ) : (
          // Standard tool display
          <Text wrap="truncate">
            <Text bold color={theme.text.primary}>
              {item.toolName}
            </Text>
            {description && (
              <Text color={theme.text.secondary}> {description}</Text>
            )}
          </Text>
        )}
      </Box>
      {/* Render SubAgent tools (for invoke_agent) with auto-scroll effect */}
      {hiddenCount > 0 && (
        <Box paddingX={1} paddingLeft={STATUS_INDICATOR_WIDTH + 2}>
          <Text color={theme.text.muted} dimColor>
            ... {hiddenCount} more tool{hiddenCount > 1 ? 's' : ''} above
          </Text>
        </Box>
      )}
      {visibleSubagentTools.map((tool) => (
        <SubagentToolItemDisplay
          key={tool.toolCallId}
          toolName={tool.toolName}
          toolInput={tool.toolInput}
          hasResult={tool.hasResult}
          isError={tool.isError}
          parentCompleted={hasResult}
        />
      ))}
    </Box>
  );
};

// Pending Tool Result Message
// Layout matches ToolResultMessage for visual consistency
// Note: Status indicator removed - success/error is shown on tool call block instead
const PendingToolResultMessage: React.FC<{ item: ToolResultHistoryItemWithoutId }> = ({ item }) => {
  // Trim and split content into lines (matches ToolResultMessage behavior)
  const content = (item.content || '').trimEnd();
  const allLines = content.split('\n');
  const truncated = allLines.length > MAX_RESULT_LINES;
  const lines = truncated ? allLines.slice(0, MAX_RESULT_LINES) : allLines;

  return (
    <Box flexDirection="column" paddingX={1} marginBottom={1}>
      {/* Content lines - indented to align with tool call description */}
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
