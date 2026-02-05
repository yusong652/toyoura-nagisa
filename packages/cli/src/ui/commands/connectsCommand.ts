/**
 * Connects Command - OAuth provider connections
 *
 * Opens a dialog to connect OAuth providers (Google, etc.).
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const connectsCommand: SlashCommand = {
  name: 'connects',
  altNames: ['connect', 'oauth'],
  description: 'Connect OAuth providers (Google / OpenAI)',
  usage:
    'Use /connects to link OAuth providers.\n\n' +
    'Supported providers:\n' +
    '  - Google: Access Gemini models via Code Assist API (Gemini CLI / Antigravity)\n' +
    '  - OpenAI: Access Codex models via ChatGPT Pro/Plus subscription\n\n' +
    'Google providers share OAuth credentials. Connect once to use with either Gemini CLI or Antigravity.\n' +
    'OpenAI Codex models are included with ChatGPT Pro/Plus subscription at no additional cost.\n' +
    'You can connect multiple accounts and set a default for each provider.',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => ({
    type: 'dialog',
    dialog: 'connects_providers',
  }),
};
