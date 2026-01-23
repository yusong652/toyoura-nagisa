/**
 * Profile Command - Switch between agent profiles
 *
 * Usage:
 *   /profile - Open profile selection dialog
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * Profile command definition
 */
export const profileCommand: SlashCommand = {
  name: 'profile',
  altNames: ['p'],
  description: 'Select agent profile',
  usage: 'Use /profile to switch between different agent profiles.\n\nProfiles optimize the agent\'s toolset for specific tasks (e.g., PFC simulation, General coding).',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'dialog',
      dialog: 'profile',
    };
  },
};
