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
import { MarkdownText } from '../MarkdownText.js';
import { useAppState } from '../../contexts/AppStateContext.js';
import { ReadToolResultDisplay } from './ReadToolResultDisplay.js';
import { formatToolDisplay, formatToolParams, getToolLayoutConfig } from '../../utils/toolFormat.js';

// Maximum lines for thinking blocks (shows last N lines when exceeded)
// Keep in sync with AssistantMessage.tsx for consistent display
const MAX_THINKING_LINES = 4;
const MAX_THINKING_LINES_FULL = Infinity;

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
const renderContentBlock = (
  block: ContentBlock,
  index: number,
  isStreaming: boolean,
  maxThinkingLines: number,
): React.ReactNode => {
  switch (block.type) {
    case 'text': {
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayText = block.text.trim();
      return (
        <Box key={`text-${index}`} flexDirection="row">
          <MarkdownText>{displayText}</MarkdownText>
          {isStreaming && (
            <Text color={theme.text.muted}>▌</Text>
          )}
        </Box>
      );
    }

    case 'thinking': {
      // Trim and limit thinking content to last N lines (auto-scroll effect)
      const { text, truncated } = getLastLines(block.thinking.trim(), maxThinkingLines);
      return (
        <Box key={`thinking-${index}`} flexDirection="column">
          {truncated && (
            <Text color={theme.text.muted}>...</Text>
          )}
          <MarkdownText dimColor baseColor={theme.message.thinking}>
            {text}
          </MarkdownText>
        </Box>
      );
    }

    default:
      return null;
  }
};

// Pending Assistant Message
const PendingAssistantMessage: React.FC<{ item: AssistantHistoryItemWithoutId }> = ({ item }) => {
  const { isFullContextMode } = useAppState();

  // Use ● (filled circle) prefix - represents Nagisa
  const prefix = '● ';
  const prefixWidth = getCachedStringWidth(prefix);

  // Determine max lines for thinking blocks based on mode
  const maxThinkingLines = isFullContextMode ? MAX_THINKING_LINES_FULL : MAX_THINKING_LINES;

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
        <Text color={theme.text.primary}>{prefix}</Text>
      </Box>
      <Box flexGrow={1} flexDirection="column">
        {content.map((block, index) => {
          const isLastTextBlock = block.type === 'text' && index === lastTextBlockIndex;
          return renderContentBlock(block, index, isStreaming && isLastTextBlock, maxThinkingLines);
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
const STATUS_INDICATOR_WIDTH = 2;  // Match "● " prefix width
// Maximum lines for tool result content (Claude Code style: 3-4 lines)
const MAX_RESULT_LINES = 3;
const MAX_RESULT_LINES_FULL = Infinity;
// Maximum SubAgent tools to show (shows most recent, older ones collapsed)
const MAX_SUBAGENT_TOOLS_SHOWN = 5;


// SubAgent Tool Item (nested under invoke_agent)
// Displayed with additional indentation
// Shows BlinkingCircle when executing, colored status when completed
const SubagentToolItemDisplay: React.FC<{
  toolName: string;
  toolInput: Record<string, unknown>;
  hasResult?: boolean;   // True when this specific tool completed
  isError?: boolean;     // True if tool execution resulted in error
  parentCompleted: boolean;  // Fallback: when invoke_agent has result, all SubAgent tools are done
}> = ({ toolName, toolInput, hasResult, isError, parentCompleted }) => {
  // Get tool-specific display formatting
  const toolDisplayResult = formatToolDisplay(toolName, toolInput);
  // Additional indent for nested tools (2 spaces)
  const SUBAGENT_INDENT = 2;

  // Tool is completed if it has its own result, or if parent (invoke_agent) is completed
  const isCompleted = hasResult === true || parentCompleted;
  const statusIcon = isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  // Color based on status: green for success, red for error, secondary for in-progress
  const statusColor = isError ? theme.status.error : theme.status.success;
  const textColor = isCompleted
    ? (isError ? theme.status.error : theme.status.success)
    : theme.text.secondary;

  // Build full display text including multiline content
  const fullDisplay = toolDisplayResult.isMultiline && toolDisplayResult.additionalLines
    ? [toolDisplayResult.display, ...toolDisplayResult.additionalLines].join('\n')
    : toolDisplayResult.display;

  return (
    <Box paddingLeft={STATUS_INDICATOR_WIDTH + SUBAGENT_INDENT}>
      <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
        {isCompleted ? (
          <Text color={statusColor}>{statusIcon}</Text>
        ) : (
          <BlinkingCircle color={theme.text.secondary} />
        )}
      </Box>
      {/* Tool-specific display format */}
      <Text wrap="wrap" bold color={textColor}>
        {fullDisplay}
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

  // Check if this is a foreground bash command (can be converted to background)
  const isBashForeground = item.toolName === 'bash' && !item.toolInput.run_in_background && !hasResult;

  // Get tool-specific display formatting
  const toolDisplayResult = formatToolDisplay(item.toolName, item.toolInput);

  // Color based on result status: success (green) or error (red)
  const statusColor = isError ? theme.status.error : theme.status.success;
  const statusIcon = isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;

  // Limit SubAgent tools displayed (show most recent, collapse older ones)
  const totalSubagentTools = subagentTools.length;
  const hiddenCount = Math.max(0, totalSubagentTools - MAX_SUBAGENT_TOOLS_SHOWN);
  const visibleSubagentTools = hiddenCount > 0
    ? subagentTools.slice(-MAX_SUBAGENT_TOOLS_SHOWN)
    : subagentTools;

  // Build full display text including multiline content
  const fullDisplay = toolDisplayResult.isMultiline && toolDisplayResult.additionalLines
    ? [toolDisplayResult.display, ...toolDisplayResult.additionalLines].join('\n')
    : toolDisplayResult.display;

  // Get tool-specific layout configuration
  const layoutConfig = getToolLayoutConfig(item.toolName);

  return (
    <Box flexDirection="column" marginBottom={layoutConfig.marginBottom}>
      <Box>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          {hasResult ? (
            <Text color={statusColor}>{statusIcon}</Text>
          ) : (
            <BlinkingCircle color={theme.status.success} />
          )}
        </Box>
        {isInvokeAgent ? (
          // Special display for invoke_agent: show SubAgent type with accent background
          <Text wrap="wrap">
            <Text bold color={theme.text.accent} inverse>
              {subagentType}
            </Text>
            {item.toolInput.description !== undefined && (
              <Text color={theme.text.secondary}> {String(item.toolInput.description)}</Text>
            )}
          </Text>
        ) : (
          // Tool-specific display format
          <Text wrap="wrap" bold color={theme.text.primary}>
            {fullDisplay}
          </Text>
        )}
      </Box>
      {/* Hint for foreground bash: ctrl+b to run in background */}
      {isBashForeground && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text color={theme.text.muted} dimColor>
            ctrl+b to run in background
          </Text>
        </Box>
      )}
      {/* Render SubAgent tools (for invoke_agent) with auto-scroll effect */}
      {hiddenCount > 0 && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH + 2}>
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
// Error results are displayed in red color
// Note: Status indicator removed - success/error is shown on tool call block instead
const PendingToolResultMessage: React.FC<{ item: ToolResultHistoryItemWithoutId }> = ({ item }) => {
  const { isFullContextMode } = useAppState();

  // Determine max lines based on mode
  const maxResultLines = isFullContextMode ? MAX_RESULT_LINES_FULL : MAX_RESULT_LINES;

  // If this is a read tool, use specialized display (removes line numbers)
  if (item.toolName === 'read' && !item.isError) {
    // Cast to full type for ReadToolResultDisplay (pending items have same structure)
    return (
      <ReadToolResultDisplay
        item={item as any}
        maxResultLines={maxResultLines}
      />
    );
  }

  // Trim and split content into lines (matches ToolResultMessage behavior)
  const content = (item.content || '').trimEnd();
  const allLines = content.split('\n');
  const truncated = allLines.length > maxResultLines;
  const lines = truncated ? allLines.slice(0, maxResultLines) : allLines;
  const hiddenLines = allLines.length - maxResultLines;

  // Error results displayed in red
  const isError = item.isError === true;
  const textColor = isError ? theme.status.error : theme.text.secondary;

  return (
    <Box flexDirection="column" paddingX={1} marginBottom={1}>
      {/* Content lines - red for errors, secondary for success */}
      {lines.map((line, index) => (
        <Box key={index} paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text wrap="truncate-end" color={textColor}>
            {line}
          </Text>
        </Box>
      ))}
      {truncated && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text color={theme.text.muted}>
            ... +{hiddenLines} lines (ctrl+o to expand)
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
