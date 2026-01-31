/**
 * Skills Command - Manage skill configurations
 *
 * Opens a dialog to view and toggle skills for the current session.
 * Each session can independently enable/disable skills.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const skillsCommand: SlashCommand = {
  name: 'skills',
  altNames: ['skill'],
  description: 'Manage skills for this session',
  usage:
    'Use /skills to view and toggle skills.\n\nSkills can be enabled or disabled per session.\nDisabled skills will not appear in system prompt or be triggerable.',
  kind: CommandKind.BUILT_IN,

  action: (context): SlashCommandActionReturn => {
    if (!context.session.currentSessionId) {
      return {
        type: 'message',
        messageType: 'error',
        content: 'No active session. Create or restore a session first.',
      };
    }

    return {
      type: 'dialog',
      dialog: 'skills',
    };
  },
};
