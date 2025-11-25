/**
 * Profile Command - Switch between agent profiles
 *
 * Usage:
 *   /profile           - Show current profile and available options
 *   /profile <name>    - Switch to specified profile (coding, lifestyle, pfc, general, disabled)
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';
import type { AgentProfileType } from '../types.js';

// Valid profile names
const VALID_PROFILES: AgentProfileType[] = ['coding', 'lifestyle', 'pfc', 'general', 'disabled'];

// Profile display info
const PROFILE_INFO: Record<AgentProfileType, { icon: string; description: string }> = {
  coding: {
    icon: '\uD83D\uDCBB',
    description: 'Code development and programming tasks'
  },
  lifestyle: {
    icon: '\uD83C\uDF1F',
    description: 'Daily life, email, calendar, and communication'
  },
  pfc: {
    icon: '\u269B\uFE0F',
    description: 'ITASCA PFC simulation specialist'
  },
  general: {
    icon: '\uD83E\uDD16',
    description: 'Full tool capabilities for complex tasks'
  },
  disabled: {
    icon: '\uD83D\uDEAB',
    description: 'Pure text conversation mode (no tools)'
  },
};

/**
 * Format profile list for display
 */
function formatProfileList(): string {
  let output = 'Available profiles:\n\n';

  for (const profileType of VALID_PROFILES) {
    const info = PROFILE_INFO[profileType];
    output += `  ${info.icon} ${profileType}\n`;
    output += `     ${info.description}\n\n`;
  }

  output += 'Usage: /profile <name> (e.g., /profile coding)';

  return output;
}

/**
 * Profile command definition
 */
export const profileCommand: SlashCommand = {
  name: 'profile',
  altNames: ['p'],
  description: 'View or switch agent profile',
  kind: CommandKind.BUILT_IN,

  action: (_context, args): SlashCommandActionReturn => {
    const trimmedArgs = args.trim().toLowerCase();

    if (!trimmedArgs) {
      // No argument - show available profiles
      return {
        type: 'message',
        messageType: 'info',
        content: formatProfileList(),
      };
    }

    // Validate profile name
    if (!VALID_PROFILES.includes(trimmedArgs as AgentProfileType)) {
      return {
        type: 'message',
        messageType: 'error',
        content: `Invalid profile: "${trimmedArgs}"\n\nValid profiles: ${VALID_PROFILES.join(', ')}`,
      };
    }

    // Return a profile switch action
    return {
      type: 'profile_switch',
      profile: trimmedArgs,
    };
  },

  // Tab completion for profile names
  completion: (_context, partialArg): string[] => {
    const partial = partialArg.toLowerCase();
    return VALID_PROFILES.filter(p => p.startsWith(partial));
  },
};
