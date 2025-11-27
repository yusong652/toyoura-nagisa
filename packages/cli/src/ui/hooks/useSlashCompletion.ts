/**
 * useSlashCompletion Hook
 * Reference: Gemini CLI ui/hooks/useSlashCompletion.ts
 *
 * Provides slash command completion functionality:
 * - Detects when input starts with "/"
 * - Filters commands based on partial input
 * - Supports sub-commands and argument completion
 * - Manages suggestion navigation state
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import type { SlashCommand, CommandContext } from '../commands/types.js';
import type { Suggestion } from '../components/SlashCommandSuggestions.js';
import { MAX_SUGGESTIONS_TO_SHOW } from '../components/SlashCommandSuggestions.js';

export interface UseSlashCompletionProps {
  /** Current input text */
  input: string;
  /** Available slash commands */
  commands: readonly SlashCommand[];
  /** Command context for completion providers */
  commandContext?: CommandContext;
  /** Whether completion is enabled */
  enabled?: boolean;
}

export interface UseSlashCompletionReturn {
  /** Current suggestions */
  suggestions: Suggestion[];
  /** Index of active suggestion (-1 for none) */
  activeIndex: number;
  /** Scroll offset for visible window */
  scrollOffset: number;
  /** Whether suggestions should be shown */
  showSuggestions: boolean;
  /** Whether loading suggestions */
  isLoading: boolean;
  /** Navigate to previous suggestion */
  navigateUp: () => void;
  /** Navigate to next suggestion */
  navigateDown: () => void;
  /** Get the selected suggestion value */
  getSelectedValue: () => string | null;
  /** Reset completion state */
  reset: () => void;
  /** Completion range in input */
  completionRange: { start: number; end: number };
}

/**
 * Check if input looks like a slash command
 */
function isSlashCommand(input: string): boolean {
  const trimmed = input.trim();
  if (!trimmed.startsWith('/')) return false;
  // Exclude line comments "//" and block comments "/*"
  if (trimmed.startsWith('//') || trimmed.startsWith('/*')) return false;
  return true;
}

/**
 * Parse a slash command input to extract command parts
 */
function parseCommandInput(input: string): {
  commandPath: string[];
  partial: string;
  hasTrailingSpace: boolean;
} {
  const trimmed = input.trim();
  if (!trimmed.startsWith('/')) {
    return { commandPath: [], partial: '', hasTrailingSpace: false };
  }

  const content = trimmed.substring(1); // Remove leading "/"
  const hasTrailingSpace = content.endsWith(' ');
  const parts = content.split(/\s+/).filter((p) => p);

  if (parts.length === 0) {
    return { commandPath: [], partial: '', hasTrailingSpace };
  }

  if (hasTrailingSpace) {
    // All parts are complete command path
    return { commandPath: parts, partial: '', hasTrailingSpace };
  }

  // Last part is partial (being typed)
  const partial = parts.pop() || '';
  return { commandPath: parts, partial, hasTrailingSpace };
}

/**
 * Find matching command in a list
 */
function findCommand(
  commands: readonly SlashCommand[],
  name: string
): SlashCommand | undefined {
  return commands.find(
    (cmd) =>
      cmd.name === name ||
      (cmd.altNames && cmd.altNames.includes(name))
  );
}

/**
 * Filter commands by prefix
 */
function filterCommandsByPrefix(
  commands: readonly SlashCommand[],
  prefix: string
): SlashCommand[] {
  const lowerPrefix = prefix.toLowerCase();
  return commands.filter((cmd) => {
    if (cmd.hidden) return false;
    if (cmd.name.toLowerCase().startsWith(lowerPrefix)) return true;
    if (cmd.altNames) {
      return cmd.altNames.some((alt) =>
        alt.toLowerCase().startsWith(lowerPrefix)
      );
    }
    return false;
  });
}

export function useSlashCompletion({
  input,
  commands,
  commandContext,
  enabled = true,
}: UseSlashCompletionProps): UseSlashCompletionReturn {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [argSuggestions, setArgSuggestions] = useState<string[]>([]);

  // Parse input and determine completion mode
  const parsed = useMemo(() => {
    if (!enabled || !isSlashCommand(input)) {
      return null;
    }
    return parseCommandInput(input);
  }, [input, enabled]);

  // Determine which commands to show and if we're completing arguments
  const { currentCommands, isArgumentCompletion, leafCommand } = useMemo(() => {
    if (!parsed) {
      return { currentCommands: [], isArgumentCompletion: false, leafCommand: null };
    }

    let currentLevel: readonly SlashCommand[] = commands;
    let leaf: SlashCommand | null = null;

    // Navigate through command path
    for (const part of parsed.commandPath) {
      const cmd = findCommand(currentLevel, part);
      if (!cmd) {
        // No matching command - show nothing
        return { currentCommands: [], isArgumentCompletion: false, leafCommand: null };
      }
      leaf = cmd;
      if (cmd.subCommands && cmd.subCommands.length > 0) {
        currentLevel = cmd.subCommands;
      } else {
        // Reached a leaf command - check for argument completion
        if (cmd.completion) {
          return { currentCommands: [], isArgumentCompletion: true, leafCommand: cmd };
        }
        return { currentCommands: [], isArgumentCompletion: false, leafCommand: cmd };
      }
    }

    // If trailing space after complete command, check for sub-commands or args
    if (parsed.hasTrailingSpace && leaf) {
      if (leaf.subCommands && leaf.subCommands.length > 0) {
        return { currentCommands: leaf.subCommands, isArgumentCompletion: false, leafCommand: leaf };
      }
      if (leaf.completion) {
        return { currentCommands: [], isArgumentCompletion: true, leafCommand: leaf };
      }
    }

    return { currentCommands: currentLevel, isArgumentCompletion: false, leafCommand: leaf };
  }, [parsed, commands]);

  // Filter commands based on partial input
  const filteredCommands = useMemo(() => {
    if (!parsed || isArgumentCompletion) return [];
    if (!parsed.partial) {
      return currentCommands.filter((cmd) => !cmd.hidden);
    }
    return filterCommandsByPrefix(currentCommands, parsed.partial);
  }, [parsed, currentCommands, isArgumentCompletion]);

  // Load argument completions asynchronously
  useEffect(() => {
    if (!isArgumentCompletion || !leafCommand?.completion || !commandContext) {
      setArgSuggestions([]);
      return;
    }

    const loadCompletions = async () => {
      setIsLoading(true);
      try {
        const partialArg = parsed?.hasTrailingSpace ? '' : (parsed?.partial || '');
        const completions = await leafCommand.completion!(commandContext, partialArg);
        setArgSuggestions(completions);
      } catch (error) {
        setArgSuggestions([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadCompletions();
  }, [isArgumentCompletion, leafCommand, commandContext, parsed]);

  // Build final suggestions list
  const suggestions: Suggestion[] = useMemo(() => {
    if (isArgumentCompletion) {
      return argSuggestions.map((arg) => ({
        label: arg,
        value: arg,
      }));
    }

    return filteredCommands.map((cmd) => ({
      label: cmd.name,
      value: cmd.name,
      description: cmd.description,
    }));
  }, [filteredCommands, isArgumentCompletion, argSuggestions]);

  // Show suggestions only when appropriate
  const showSuggestions = useMemo(() => {
    if (!enabled || !parsed) return false;
    return suggestions.length > 0;
  }, [enabled, parsed, suggestions.length]);

  // Reset state when suggestions change
  useEffect(() => {
    setActiveIndex(suggestions.length > 0 ? 0 : -1);
    setScrollOffset(0);
  }, [suggestions.length, input]);

  // Navigation
  const navigateUp = useCallback(() => {
    if (suggestions.length === 0) return;
    setActiveIndex((prev) => {
      const newIndex = prev <= 0 ? suggestions.length - 1 : prev - 1;
      // Adjust scroll
      setScrollOffset((prevScroll) => {
        if (newIndex === suggestions.length - 1) {
          return Math.max(0, suggestions.length - MAX_SUGGESTIONS_TO_SHOW);
        }
        if (newIndex < prevScroll) {
          return newIndex;
        }
        return prevScroll;
      });
      return newIndex;
    });
  }, [suggestions.length]);

  const navigateDown = useCallback(() => {
    if (suggestions.length === 0) return;
    setActiveIndex((prev) => {
      const newIndex = prev >= suggestions.length - 1 ? 0 : prev + 1;
      // Adjust scroll
      setScrollOffset((prevScroll) => {
        if (newIndex === 0) return 0;
        const visibleEnd = prevScroll + MAX_SUGGESTIONS_TO_SHOW;
        if (newIndex >= visibleEnd) {
          return newIndex - MAX_SUGGESTIONS_TO_SHOW + 1;
        }
        return prevScroll;
      });
      return newIndex;
    });
  }, [suggestions.length]);

  const getSelectedValue = useCallback(() => {
    if (activeIndex < 0 || activeIndex >= suggestions.length) {
      return null;
    }
    return suggestions[activeIndex].value;
  }, [activeIndex, suggestions]);

  const reset = useCallback(() => {
    setActiveIndex(-1);
    setScrollOffset(0);
    setArgSuggestions([]);
  }, []);

  // Calculate completion range
  const completionRange = useMemo(() => {
    if (!parsed) return { start: 0, end: 0 };

    const trimmedStart = input.indexOf('/');
    if (trimmedStart === -1) return { start: 0, end: 0 };

    if (isArgumentCompletion) {
      // Replace from after the command
      const commandEnd = input.lastIndexOf(' ');
      if (commandEnd === -1) {
        return { start: input.length, end: input.length };
      }
      return { start: commandEnd + 1, end: input.length };
    }

    // Replace the partial command
    if (parsed.partial) {
      const partialStart = input.lastIndexOf(parsed.partial);
      return { start: partialStart, end: input.length };
    }

    // Append after trailing space
    return { start: input.length, end: input.length };
  }, [input, parsed, isArgumentCompletion]);

  return {
    suggestions,
    activeIndex,
    scrollOffset,
    showSuggestions,
    isLoading,
    navigateUp,
    navigateDown,
    getSelectedValue,
    reset,
    completionRange,
  };
}
