/**
 * Theme Command - Switch between color themes
 *
 * Usage:
 *   /theme - Open theme selection dialog
 *   /theme <name> - Switch to specific theme
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';
import { themeManager, themes, type ThemeName } from '../themes/index.js';

const themeNames = Object.keys(themes) as ThemeName[];

/**
 * Theme command definition
 */
export const themeCommand: SlashCommand = {
  name: 'theme',
  altNames: ['t'],
  description: 'Switch color theme',
  kind: CommandKind.BUILT_IN,

  action: (_context, args): SlashCommandActionReturn | void => {
    const themeName = args.trim().toLowerCase();

    // If a theme name is provided, switch directly
    if (themeName && themeNames.includes(themeName as ThemeName)) {
      themeManager.setTheme(themeName as ThemeName);
      return;
    }

    // If invalid theme name provided, show error
    if (themeName) {
      return {
        type: 'message',
        messageType: 'error',
        content: `Unknown theme: ${themeName}. Available: ${themeNames.join(', ')}`,
      };
    }

    // No args - open theme selection dialog
    return {
      type: 'dialog',
      dialog: 'theme',
    };
  },

  completion: (_context, partialArg): string[] => {
    const partial = partialArg.toLowerCase();
    return themeNames.filter((name) => name.startsWith(partial));
  },
};
