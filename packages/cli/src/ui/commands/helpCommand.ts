/**
 * Help Command - Display available commands and keyboard shortcuts
 */

import { CommandKind, type SlashCommand, type SlashCommandActionReturn } from './types.js';

// All registered commands (will be injected)
let registeredCommands: readonly SlashCommand[] = [];

/**
 * Set the registered commands for help display
 */
export function setHelpCommands(commands: readonly SlashCommand[]): void {
  registeredCommands = commands;
}

/**
 * Format the help message
 */
function formatHelpMessage(): string {
  const lines: string[] = [];

  // Header
  lines.push('Nagisa CLI Help');
  lines.push('');

  // Commands section
  lines.push('Commands:');
  const visibleCommands = registeredCommands.filter((cmd) => !cmd.hidden);
  for (const cmd of visibleCommands) {
    const aliases = cmd.altNames?.length ? ` (${cmd.altNames.map(a => '/' + a).join(', ')})` : '';
    lines.push(`  /${cmd.name}${aliases}`);
    lines.push(`      ${cmd.description}`);
  }

  lines.push('');

  // Keyboard shortcuts section
  lines.push('Keyboard Shortcuts:');
  lines.push('');
  lines.push('  Input:');
  lines.push('    Enter           Submit message');
  lines.push('    Ctrl+J          Insert newline');
  lines.push('    Shift+Enter     Insert newline');
  lines.push('    \\ + Enter       Insert newline');
  lines.push('    Ctrl+U          Delete to line start');
  lines.push('    Ctrl+K          Delete to line end');
  lines.push('    Ctrl+W          Delete word backward');
  lines.push('    Ctrl+A / Home   Move to line start');
  lines.push('    Ctrl+E / End    Move to line end');
  lines.push('');
  lines.push('  App:');
  lines.push('    Ctrl+C          Cancel request / Quit');
  lines.push('    Escape          Cancel request');
  lines.push('');
  lines.push('  Scrolling:');
  lines.push('    Shift+Up        Scroll up');
  lines.push('    Shift+Down      Scroll down');
  lines.push('    Page Up         Page up');
  lines.push('    Page Down       Page down');
  lines.push('    Home            Scroll to top');
  lines.push('    End             Scroll to bottom');
  lines.push('');
  lines.push('  Suggestions:');
  lines.push('    Up/Down         Navigate suggestions');
  lines.push('    Tab             Accept suggestion');
  lines.push('    Enter           Accept and execute');
  lines.push('    Escape          Dismiss suggestions');
  lines.push('');
  lines.push('  File Mentions:');
  lines.push('    @               Start file mention');
  lines.push('    Tab/Enter       Accept file suggestion');

  return lines.join('\n');
}

/**
 * Help command definition
 */
export const helpCommand: SlashCommand = {
  name: 'help',
  altNames: ['h', '?'],
  description: 'Show available commands and keyboard shortcuts',
  kind: CommandKind.BUILT_IN,

  action: (): SlashCommandActionReturn => {
    return {
      type: 'message',
      messageType: 'info',
      content: formatHelpMessage(),
    };
  },
};
