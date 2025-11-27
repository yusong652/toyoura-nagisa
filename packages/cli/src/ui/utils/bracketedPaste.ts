/**
 * Bracketed Paste Mode utilities
 * Reference: Gemini CLI ui/utils/bracketedPaste.ts
 *
 * Bracketed paste mode is a terminal feature that wraps pasted text
 * with special escape sequences (\x1b[200~ and \x1b[201~).
 * This allows the application to distinguish between typed and pasted text,
 * enabling proper handling of multiline content without triggering
 * commands or special key processing.
 */

const ENABLE_BRACKETED_PASTE = '\x1b[?2004h';
const DISABLE_BRACKETED_PASTE = '\x1b[?2004l';

export const enableBracketedPaste = (): void => {
  process.stdout.write(ENABLE_BRACKETED_PASTE);
};

export const disableBracketedPaste = (): void => {
  process.stdout.write(DISABLE_BRACKETED_PASTE);
};
