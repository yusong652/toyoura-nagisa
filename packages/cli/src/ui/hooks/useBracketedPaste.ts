/**
 * useBracketedPaste Hook
 * Reference: Gemini CLI ui/hooks/useBracketedPaste.ts
 *
 * Enables and disables bracketed paste mode in the terminal.
 * This hook ensures that bracketed paste mode is enabled when the component
 * mounts and disabled when it unmounts or when the process exits.
 *
 * With bracketed paste mode enabled, multiline content can be pasted
 * correctly, including code snippets from bash or other sources.
 */

import { useEffect } from 'react';
import {
  disableBracketedPaste,
  enableBracketedPaste,
} from '../utils/bracketedPaste.js';

export const useBracketedPaste = (): void => {
  const cleanup = (): void => {
    disableBracketedPaste();
  };

  useEffect(() => {
    enableBracketedPaste();

    process.on('exit', cleanup);
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);

    return () => {
      cleanup();
      process.removeListener('exit', cleanup);
      process.removeListener('SIGINT', cleanup);
      process.removeListener('SIGTERM', cleanup);
    };
  }, []);
};
