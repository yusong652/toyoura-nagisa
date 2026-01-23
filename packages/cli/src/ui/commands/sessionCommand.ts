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
  usage: 'Use /session to open the session manager.\n\nCommands:\n  create   Create a new chat session\n  restore  Switch to an existing session\n  delete   Remove an old session',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'session',
    };
  },
};
