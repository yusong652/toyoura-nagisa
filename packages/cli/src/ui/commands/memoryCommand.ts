/**
 * Memory Command - Toggle long-term memory feature
 *
 * Opens a dialog to select memory on/off.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * Memory command definition
 */
export const memoryCommand: SlashCommand = {
  name: 'memory',
  altNames: ['m'],
  description: 'Toggle long-term memory',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'memory',
    };
  },
};
