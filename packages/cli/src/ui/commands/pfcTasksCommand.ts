/**
 * PFC Tasks Command - List and inspect PFC simulation tasks
 *
 * Opens a SelectDialog to browse tasks, then shows detailed output on selection.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * PFC tasks command definition
 */
export const pfcTasksCommand: SlashCommand = {
  name: 'pfc-list-tasks',
  altNames: ['pfc-tasks', 'pfctasks'],
  description: 'List and inspect PFC simulation tasks',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'pfc_tasks',
    };
  },
};
