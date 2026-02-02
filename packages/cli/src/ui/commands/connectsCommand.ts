/**
 * Connects Command - OAuth provider connections
 *
 * Opens a dialog to connect OAuth providers (Google, etc.).
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const connectsCommand: SlashCommand = {
  name: 'connects',
  altNames: ['connect', 'oauth'],
  description: 'Connect OAuth providers (Google Gemini CLI / Antigravity)',
  usage:
    'Use /connects to link OAuth providers.\n\n' +
    'Supported providers:\n' +
    '  - Google Gemini CLI: Access Gemini models via Code Assist API\n' +
    '  - Google Antigravity: Access Gemini + Claude models with endpoint fallback\n\n' +
    'Both providers share the same OAuth credentials. Connect once to use with either provider.\n' +
    'You can also connect multiple accounts and set a default for quota checks.',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => ({
    type: 'dialog',
    dialog: 'connects_providers',
  }),
};
