/**
 * MCP Servers Command - Manage MCP server configurations
 *
 * Opens a dialog to view and toggle MCP servers for the current session.
 * Each session can independently enable/disable MCP servers.
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

export const mcpsCommand: SlashCommand = {
  name: 'mcps',
  altNames: ['mcp-servers', 'mcp'],
  description: 'Manage MCP servers for this session',
  usage:
    'Use /mcps to view and toggle MCP servers.\n\nServers can be enabled or disabled per session.\nDisabled servers will not provide tools during chat.',
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
      dialog: 'mcp_servers',
    };
  },
};
