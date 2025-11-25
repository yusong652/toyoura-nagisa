/**
 * CLI Color Definitions
 * Reference: Gemini CLI semantic-colors.ts and themes/semantic-tokens.ts
 */

// Base ANSI-friendly color palette (works better in terminals)
export const colors = {
  // Primary colors (using ANSI-friendly values)
  primary: 'magenta',      // Purple equivalent
  secondary: 'cyan',       // Cyan
  accent: 'yellow',        // Accent

  // Status colors
  success: 'green',
  error: 'red',
  warning: 'yellow',
  info: 'blue',

  // Text colors
  text: 'white',
  textDim: 'gray',
  textMuted: 'gray',

  // Background colors
  bg: 'black',
  bgLight: 'gray',

  // Role colors (matching Gemini CLI style)
  user: 'cyan',            // User messages
  assistant: 'white',      // Assistant messages (Gemini uses white)
  system: 'gray',
  tool: 'yellow',
  thinking: 'magenta',
} as const;

// Semantic theme matching Gemini CLI SemanticColors interface
export const theme = {
  text: {
    primary: colors.text,          // Main text color
    secondary: colors.textDim,     // Dimmed text
    muted: colors.textMuted,       // Very dim text
    accent: colors.accent,         // Highlights (yellow like Gemini)
    link: colors.secondary,        // Links (cyan)
    response: colors.text,         // AI response text
  },

  status: {
    success: colors.success,       // ✓ checkmarks
    error: colors.error,           // ✕ errors
    warning: colors.warning,       // Tool confirmations
    info: colors.info,
  },

  message: {
    user: colors.user,             // User input prefix
    assistant: colors.text,        // AI response (white text)
    system: colors.system,
    tool: colors.tool,             // Tool names
    thinking: colors.thinking,     // Thinking content
  },

  ui: {
    border: 'gray',
    borderFocus: colors.primary,
    spinner: colors.secondary,
    symbol: 'gray',                // Like Gemini's ui.symbol
  },

  // Border colors matching Gemini CLI
  border: {
    default: 'gray',
    focused: colors.secondary,
  },
} as const;

// Tool status symbols (matching Gemini CLI TOOL_STATUS constants)
export const TOOL_STATUS = {
  PENDING: 'o',
  EXECUTING: '*',
  SUCCESS: '✓',
  CONFIRMING: '?',
  CANCELED: '✕',
  ERROR: '✕',
} as const;
