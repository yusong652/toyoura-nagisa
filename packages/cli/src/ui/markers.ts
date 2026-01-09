/**
 * Status markers and symbols for CLI UI
 * These are visual indicators, not colors
 */

// Tool status symbols
export const TOOL_STATUS = {
  PENDING: '○',
  SUCCESS: '●',
  ERROR: '●',
} as const;

// Tool result prefix (Claude Code style: ⎿)
export const TOOL_RESULT_PREFIX = '⎿';
