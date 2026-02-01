/**
 * Connects Command - OAuth provider connections
 *
 * Opens a dialog to connect OAuth providers (Google, etc.).
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const connectsCommand: SlashCommand = {
  name: 'connects',
  altNames: ['connect', 'oauth'],
  description: 'Connect OAuth providers and manage accounts',
  usage:
    'Use /connects to link OAuth providers.\n\nConnect multiple accounts and set a default for quota checks.',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => ({
    type: 'dialog',
    dialog: 'connects_providers',
  }),
};
