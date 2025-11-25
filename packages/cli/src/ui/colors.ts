/**
 * CLI Color Definitions
 * Reference: Gemini CLI semantic-colors.ts
 */

// Base color palette
export const colors = {
  // Primary colors
  primary: '#7C3AED',      // Purple
  secondary: '#06B6D4',    // Cyan
  accent: '#F59E0B',       // Amber

  // Status colors
  success: '#10B981',      // Green
  error: '#EF4444',        // Red
  warning: '#F59E0B',      // Amber
  info: '#3B82F6',         // Blue

  // Text colors
  text: '#E5E7EB',         // Light gray
  textDim: '#9CA3AF',      // Gray
  textMuted: '#6B7280',    // Dark gray

  // Background colors
  bg: '#1F2937',           // Dark
  bgLight: '#374151',      // Lighter dark

  // Role colors
  user: '#3B82F6',         // Blue
  assistant: '#10B981',    // Green
  system: '#9CA3AF',       // Gray
  tool: '#F59E0B',         // Amber
  thinking: '#8B5CF6',     // Purple
} as const;

// Semantic theme
export const theme = {
  text: {
    primary: colors.text,
    secondary: colors.textDim,
    muted: colors.textMuted,
    accent: colors.accent,
    link: colors.secondary,
  },

  status: {
    success: colors.success,
    error: colors.error,
    warning: colors.warning,
    info: colors.info,
  },

  message: {
    user: colors.user,
    assistant: colors.assistant,
    system: colors.system,
    tool: colors.tool,
    thinking: colors.thinking,
  },

  ui: {
    border: colors.textMuted,
    borderFocus: colors.primary,
    spinner: colors.secondary,
  },
} as const;
