/**
 * Session Command - Manage chat sessions
 *
 * Opens a dialog to select session action (create/restore/delete).
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * Session command definition
 */
export const sessionCommand: SlashCommand = {
  name: 'session',
  altNames: ['s'],
  description: 'Manage chat sessions',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'session',
    };
  },
};
