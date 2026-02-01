/**
 * Quota Command - Display Gemini quota usage
 *
 * Opens a dialog to show current Google Gemini quota.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const quotaCommand: SlashCommand = {
  name: 'quota',
  altNames: ['usage'],
  description: 'Show Google Gemini quota usage',
  usage: 'Use /quota to view Gemini quota usage for the default account.',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => ({
    type: 'dialog',
    dialog: 'quota_display',
  }),
};
