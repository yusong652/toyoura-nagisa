/**
 * Tool Display Formatting Utilities
 *
 * Claude Code style tool parameter display:
 * - Function call syntax: ToolName(param1: "value1", param2: "value2")
 * - All parameters visible at a glance
 * - String values quoted, long strings truncated
 */

/** Maximum length for individual parameter values before truncation */
const MAX_PARAM_VALUE_LENGTH = 120;

/** Parameters to skip in display (too verbose or internal) */
const SKIP_PARAMS = new Set(['old_string', 'new_string', 'content', 'code']);

/**
 * Format a single parameter value for display
 */
function formatParamValue(value: unknown): string {
  if (typeof value === 'string') {
    // Truncate long strings
    if (value.length > MAX_PARAM_VALUE_LENGTH) {
      return `"${value.slice(0, MAX_PARAM_VALUE_LENGTH - 3)}..."`;
    }
    return `"${value}"`;
  }
  if (typeof value === 'boolean' || typeof value === 'number') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  if (value === null || value === undefined) {
    return String(value);
  }
  // Object - show abbreviated
  return '{...}';
}

/**
 * Format tool parameters in Claude Code style
 *
 * @example
 * formatToolParams({ pattern: "*.tsx", path: "/src" })
 * // Returns: 'pattern: "*.tsx", path: "/src"'
 *
 * @example
 * formatToolParams({ file_path: "/src/App.tsx", old_string: "...", new_string: "..." })
 * // Returns: 'file_path: "/src/App.tsx"' (skips verbose params)
 */
export function formatToolParams(input: Record<string, unknown>): string {
  const params = Object.entries(input)
    .filter(([key, value]) => value !== undefined && !SKIP_PARAMS.has(key))
    .map(([key, value]) => `${key}: ${formatParamValue(value)}`);

  return params.join(', ');
}

/**
 * Get file name from path (for edit/write tools)
 */
export function getFileName(filePath: string): string {
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}
