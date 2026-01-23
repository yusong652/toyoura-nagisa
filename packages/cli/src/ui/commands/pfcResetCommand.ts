/**
 * PFC Reset Command - Reset PFC workspace state for testing
 *
 * Opens a confirmation dialog before clearing:
 * - Quick console scripts and counter
 * - All task history (memory + disk)
 * - Git pfc-executions branch (all execution snapshots)
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * PFC reset command definition
 */
export const pfcResetCommand: SlashCommand = {
  name: 'pfc-reset',
  altNames: ['pfc-init', 'pfcreset'],
  description: 'Reset PFC workspace (clears all history)',
  usage: 'Use /pfc-reset to completely reset the PFC workspace.\n\nWARNING: This is a destructive action that will clear:\n  - All console script history\n  - All tracked tasks\n  - The git pfc-executions branch (snapshots)',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'pfc_reset',
    };
  },
};
