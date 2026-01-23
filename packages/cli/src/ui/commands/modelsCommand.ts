/**
 * Models Command - Select LLM provider and models
 *
 * Opens a dialog to choose provider, primary model, and secondary model
 * for the current session.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const modelsCommand: SlashCommand = {
  name: 'models',
  description: 'Select LLM provider and models for this session',
  usage: 'Use /models to configure LLM settings for the current session.\n\nYou can select:\n  1. Provider (Google, Anthropic, OpenAI, etc.)\n  2. Primary Model (for main chat)\n  3. Secondary Model (for sub-agents)',
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
      dialog: 'models_provider',
    };
  },
};
