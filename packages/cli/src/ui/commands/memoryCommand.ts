/**
 * Memory Command - Toggle long-term memory feature
 *
 * Usage:
 *   /memory           - Show current memory status
 *   /memory on        - Enable memory
 *   /memory off       - Disable memory
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

/**
 * Memory command definition
 */
export const memoryCommand: SlashCommand = {
  name: 'memory',
  altNames: ['m'],
  description: 'Toggle long-term memory feature',
  kind: CommandKind.BUILT_IN,

  action: (_context, args): SlashCommandActionReturn => {
    const trimmedArgs = args.trim().toLowerCase();

    if (!trimmedArgs) {
      // No argument - show help
      return {
        type: 'message',
        messageType: 'info',
        content: 'Memory: Controls long-term conversation memory\n\nUsage:\n  /memory on   - Enable memory\n  /memory off  - Disable memory\n\nWhen enabled, the AI can recall previous conversations.',
      };
    }

    if (trimmedArgs === 'on' || trimmedArgs === 'enable' || trimmedArgs === '1' || trimmedArgs === 'true') {
      return {
        type: 'memory_toggle',
        enabled: true,
      };
    }

    if (trimmedArgs === 'off' || trimmedArgs === 'disable' || trimmedArgs === '0' || trimmedArgs === 'false') {
      return {
        type: 'memory_toggle',
        enabled: false,
      };
    }

    return {
      type: 'message',
      messageType: 'error',
      content: `Invalid argument: "${trimmedArgs}"\n\nUsage: /memory on|off`,
    };
  },

  // Tab completion
  completion: (_context, partialArg): string[] => {
    const options = ['on', 'off'];
    const partial = partialArg.toLowerCase();
    return options.filter(o => o.startsWith(partial));
  },
};
