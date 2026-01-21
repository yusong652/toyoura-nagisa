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
