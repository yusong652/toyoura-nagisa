/**
 * useSlashCommandProcessor Hook
 * Reference: Gemini CLI ui/hooks/slashCommandProcessor.ts
 *
 * Manages slash command registration and execution:
 * - Loads and registers available commands
 * - Matches input to commands (including aliases)
 * - Executes command actions with context
 * - Returns action results for UI handling
 */

import { useCallback, useMemo } from 'react';
import type {
  SlashCommand,
  CommandContext,
  SlashCommandActionReturn,
} from '../commands/types.js';
import { profileCommand } from '../commands/profileCommand.js';
import { memoryCommand } from '../commands/memoryCommand.js';
import { sessionCommand } from '../commands/sessionCommand.js';
import { themeCommand } from '../commands/themeCommand.js';

// Built-in commands
const BUILT_IN_COMMANDS: SlashCommand[] = [
  profileCommand,
  memoryCommand,
  sessionCommand,
  themeCommand,
];

export interface UseSlashCommandProcessorProps {
  /** Command context to pass to command actions */
  context: Partial<CommandContext>;
}

export interface UseSlashCommandProcessorReturn {
  /** All available commands */
  commands: readonly SlashCommand[];
  /** Process a slash command and return the result */
  processCommand: (
    name: string,
    args: string
  ) => Promise<SlashCommandActionReturn | null>;
  /** Get command context for completion */
  commandContext: CommandContext;
}

/**
 * Find a command by name (including aliases)
 */
function findCommand(
  commands: readonly SlashCommand[],
  name: string
): SlashCommand | undefined {
  const lowerName = name.toLowerCase();
  return commands.find((cmd) => {
    if (cmd.name.toLowerCase() === lowerName) return true;
    if (cmd.altNames) {
      return cmd.altNames.some((alt) => alt.toLowerCase() === lowerName);
    }
    return false;
  });
}

/**
 * Navigate to a subcommand if path contains multiple parts
 */
function navigateToCommand(
  commands: readonly SlashCommand[],
  path: string[]
): { command: SlashCommand | null; remainingArgs: string } {
  if (path.length === 0) {
    return { command: null, remainingArgs: '' };
  }

  let currentLevel = commands;
  let command: SlashCommand | null = null;

  for (let i = 0; i < path.length; i++) {
    const part = path[i];
    const found = findCommand(currentLevel, part);

    if (!found) {
      // No command found at this level
      // Return previous command with remaining path as args
      return {
        command,
        remainingArgs: path.slice(i).join(' '),
      };
    }

    command = found;

    if (found.subCommands && found.subCommands.length > 0 && i < path.length - 1) {
      // Has subcommands and more path parts - continue navigating
      currentLevel = found.subCommands;
    } else {
      // Reached a leaf or end of path
      return {
        command,
        remainingArgs: path.slice(i + 1).join(' '),
      };
    }
  }

  return { command, remainingArgs: '' };
}

export function useSlashCommandProcessor({
  context,
}: UseSlashCommandProcessorProps): UseSlashCommandProcessorReturn {
  // Combine built-in commands (could add extension loading later)
  const commands = useMemo(() => {
    return BUILT_IN_COMMANDS;
  }, []);

  // Build full command context
  const commandContext = useMemo((): CommandContext => {
    return {
      invocation: undefined,
      services: context.services || {
        connectionManager: {
          send: () => {},
          connectToSession: async () => {},
          disconnect: () => {},
        },
        sessionManager: {
          createSession: async () => '',
          loadSessions: async () => [],
          deleteSession: async () => {},
        },
      },
      ui: context.ui || {
        addItem: () => {},
        clear: () => {},
        setPendingItem: () => {},
        reloadCommands: () => {},
      },
      session: context.session || {
        currentSessionId: null,
        stats: { inputTokens: 0, outputTokens: 0, totalTokens: 0 },
      },
    };
  }, [context]);

  // Process a slash command
  const processCommand = useCallback(
    async (name: string, args: string): Promise<SlashCommandActionReturn | null> => {
      // Parse the full command path
      const fullPath = args ? `${name} ${args}` : name;
      const pathParts = fullPath.split(/\s+/).filter((p) => p);

      // Navigate to the target command
      const { command, remainingArgs } = navigateToCommand(commands, pathParts);

      if (!command) {
        return {
          type: 'message',
          messageType: 'error',
          content: `Unknown command: /${name}\n\nType / to see available commands.`,
        };
      }

      if (!command.action) {
        // Command has no action (maybe just a namespace for subcommands)
        if (command.subCommands && command.subCommands.length > 0) {
          const subNames = command.subCommands
            .filter((s) => !s.hidden)
            .map((s) => s.name)
            .join(', ');
          return {
            type: 'message',
            messageType: 'info',
            content: `/${command.name} subcommands: ${subNames}\n\nUsage: /${command.name} <subcommand>`,
          };
        }
        return null;
      }

      // Build invocation context
      const fullContext: CommandContext = {
        ...commandContext,
        invocation: {
          raw: `/${fullPath}`,
          name: command.name,
          args: remainingArgs,
        },
      };

      try {
        const result = await command.action(fullContext, remainingArgs);
        return result || null;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          type: 'message',
          messageType: 'error',
          content: `Error executing /${command.name}: ${message}`,
        };
      }
    },
    [commands, commandContext]
  );

  return {
    commands,
    processCommand,
    commandContext,
  };
}
