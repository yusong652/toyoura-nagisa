/**
 * Tool Display Formatting Utilities
 *
 * Claude Code style tool display with tool-specific formatting:
 * - Bash: Bash(command content) - multiline truncated to 2 lines
 * - Read: Read(file/path) - direct path without param name
 * - Edit/Write: Edit(file/path) - direct path
 * - Glob: Glob(pattern: "*.tsx")
 * - Grep: Grep(pattern: "xxx", path: "xxx")
 * - Others: ToolName(param1: "value1", param2: "value2")
 */

/** Maximum lines for multiline command display */
const MAX_COMMAND_LINES = 2;

/** Maximum length for single-line command before truncation */
const MAX_COMMAND_LENGTH = 80;

/** Maximum length for individual parameter values before truncation */
const MAX_PARAM_VALUE_LENGTH = 60;

/** Parameters to skip in generic display (too verbose) */
const SKIP_PARAMS = new Set(['old_string', 'new_string', 'content', 'code']);

/**
 * Tool display result with optional multiline support
 */
export interface ToolDisplayResult {
  /** Primary display line (tool name + formatted args) */
  display: string;
  /** Whether the display spans multiple lines */
  isMultiline: boolean;
  /** Additional lines for multiline display (without tool name) */
  additionalLines?: string[];
}

/**
 * Format Bash command for display
 * - Multiline: show first 2 lines + ellipsis
 * - Single line: show command directly (truncated if too long)
 */
function formatBashCommand(command: string): ToolDisplayResult {
  const lines = command.split('\n');

  if (lines.length > MAX_COMMAND_LINES) {
    // Multiline command: show first lines + ellipsis
    const firstLines = lines.slice(0, MAX_COMMAND_LINES);
    return {
      display: `Bash(${firstLines[0]}`,
      isMultiline: true,
      additionalLines: [
        ...firstLines.slice(1).map(line => `    ${line}`),
        '    ...)',
      ],
    };
  }

  if (lines.length === 2) {
    // Two-line command
    return {
      display: `Bash(${lines[0]}`,
      isMultiline: true,
      additionalLines: [`    ${lines[1]})`],
    };
  }

  // Single line command
  const truncated = command.length > MAX_COMMAND_LENGTH
    ? command.slice(0, MAX_COMMAND_LENGTH - 3) + '...'
    : command;

  return {
    display: `Bash(${truncated})`,
    isMultiline: false,
  };
}

/**
 * Format file path for display (Read, Edit, Write tools)
 * Shows relative path from workspace if possible
 */
function formatFilePath(filePath: string): string {
  // Try to extract relative path (after common workspace patterns)
  const workspacePatterns = [
    /.*\/toyoura-nagisa\/(.*)/,
    /.*\/packages\/(.*)/,
  ];

  for (const pattern of workspacePatterns) {
    const match = filePath.match(pattern);
    if (match) {
      return match[1];
    }
  }

  // Fallback: show last 60 chars if too long
  if (filePath.length > MAX_PARAM_VALUE_LENGTH) {
    return '...' + filePath.slice(-(MAX_PARAM_VALUE_LENGTH - 3));
  }

  return filePath;
}

/**
 * Format a single parameter value for display
 */
function formatParamValue(value: unknown): string {
  if (typeof value === 'string') {
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
  return '{...}';
}

/**
 * Format tool call for display with tool-specific logic
 *
 * @example
 * formatToolDisplay('bash', { command: 'git status' })
 * // Returns: { display: 'Bash(git status)', isMultiline: false }
 *
 * @example
 * formatToolDisplay('read', { file_path: '/path/to/file.ts' })
 * // Returns: { display: 'Read(path/to/file.ts)', isMultiline: false }
 */
export function formatToolDisplay(
  toolName: string,
  input: Record<string, unknown>
): ToolDisplayResult {
  const normalizedName = toolName.toLowerCase();

  switch (normalizedName) {
    case 'bash': {
      const command = String(input.command || '');
      return formatBashCommand(command);
    }

    case 'read': {
      // Backend uses 'path' parameter, not 'file_path'
      const filePath = String(input.path || input.file_path || '');
      return {
        display: `Read(${formatFilePath(filePath)})`,
        isMultiline: false,
      };
    }

    case 'edit': {
      const filePath = String(input.file_path || input.path || '');
      return {
        display: `Edit(${formatFilePath(filePath)})`,
        isMultiline: false,
      };
    }

    case 'write': {
      const filePath = String(input.file_path || input.path || '');
      return {
        display: `Write(${formatFilePath(filePath)})`,
        isMultiline: false,
      };
    }

    case 'glob': {
      const pattern = String(input.pattern || '');
      const path = input.path ? `, path: "${formatFilePath(String(input.path))}"` : '';
      return {
        display: `Glob(pattern: "${pattern}"${path})`,
        isMultiline: false,
      };
    }

    case 'grep': {
      const pattern = String(input.pattern || '');
      const path = input.path ? `, path: "${formatFilePath(String(input.path))}"` : '';
      return {
        display: `Grep(pattern: "${pattern}"${path})`,
        isMultiline: false,
      };
    }

    case 'bash_output': {
      const bashId = String(input.bash_id || '');
      return {
        display: `BashOutput(${bashId})`,
        isMultiline: false,
      };
    }

    case 'kill_shell': {
      const shellId = String(input.shell_id || '');
      return {
        display: `KillShell(${shellId})`,
        isMultiline: false,
      };
    }

    case 'web_search': {
      const query = String(input.query || '');
      const truncatedQuery = query.length > MAX_PARAM_VALUE_LENGTH
        ? query.slice(0, MAX_PARAM_VALUE_LENGTH - 3) + '...'
        : query;
      return {
        display: `WebSearch(${truncatedQuery})`,
        isMultiline: false,
      };
    }

    default: {
      // Generic format for other tools
      const params = formatToolParams(input);
      // Capitalize first letter of tool name
      const displayName = toolName.charAt(0).toUpperCase() + toolName.slice(1);
      return {
        display: params ? `${displayName}(${params})` : `${displayName}()`,
        isMultiline: false,
      };
    }
  }
}

/**
 * Format tool parameters in generic style (for tools without specific formatting)
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

/**
 * Tool display configuration
 * Controls layout properties like margins for each tool type
 */
export interface ToolLayoutConfig {
  /** Bottom margin after tool call (0 = result displays inline) */
  marginBottom: number;
}

const DEFAULT_LAYOUT: ToolLayoutConfig = {
  marginBottom: 1,
};

/**
 * Get layout configuration for a specific tool
 * Allows tool-specific customization of display properties
 */
export function getToolLayoutConfig(toolName: string): ToolLayoutConfig {
  switch (toolName.toLowerCase()) {
    // Read tool: result displays inline (no margin)
    case 'read':
      return { marginBottom: 0 };

    // Glob tool: result displays inline (file list)
    case 'glob':
      return { marginBottom: 0 };

    // Grep tool: result displays inline (matches)
    case 'grep':
      return { marginBottom: 0 };

    // Default: standard margin
    default:
      return DEFAULT_LAYOUT;
  }
}
