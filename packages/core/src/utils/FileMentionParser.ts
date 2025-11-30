/**
 * File mention parsing utilities for @ mention autocomplete
 *
 * Provides pure parsing logic for detecting and extracting @ file mentions
 * from text input. This module contains platform-agnostic parsing functions
 * that can be used in both web and CLI environments.
 *
 * @module @toyoura-nagisa/core/utils/FileMentionParser
 */

/**
 * File mention match result
 */
export interface FileMentionMatch {
  /** Start position of @ character */
  atPosition: number
  /** Extracted query string after @ */
  query: string
  /** Current cursor position */
  cursor: number
}

/**
 * Find @ character position before cursor
 *
 * Searches backwards from the cursor position to find the nearest @ character
 * that is not separated by whitespace. This function respects mention boundaries
 * (whitespace and newlines).
 *
 * @param text - Input text to search
 * @param cursor - Current cursor position
 * @returns Position of @ character, or -1 if not found
 *
 * @example
 * ```typescript
 * findAtSignPosition("Hello @file", 11) // 6
 * findAtSignPosition("@file test", 5) // 0
 * findAtSignPosition("Hello world", 11) // -1
 * findAtSignPosition("Hello @file test", 16) // -1 (separated by space)
 * ```
 */
export function findAtSignPosition(text: string, cursor: number): number {
  // Search backwards from cursor for @ character
  for (let i = cursor - 1; i >= 0; i--) {
    const char = text[i]

    // Found @ character
    if (char === '@') {
      return i
    }

    // Stop at whitespace or newline (@ mention boundary)
    if (char === ' ' || char === '\n' || char === '\t') {
      return -1
    }
  }

  return -1
}

/**
 * Extract query string after @ character
 *
 * Extracts the text between the @ character and the cursor position.
 * This is the query string that will be used for file searching.
 *
 * @param text - Input text
 * @param cursor - Current cursor position
 * @param atPosition - Position of @ character
 * @returns Extracted query string
 *
 * @example
 * ```typescript
 * extractQuery("Hello @sample", 13, 6) // "sample"
 * extractQuery("@test", 5, 0) // "test"
 * extractQuery("@", 1, 0) // ""
 * ```
 */
export function extractQuery(
  text: string,
  cursor: number,
  atPosition: number
): string {
  if (atPosition === -1) return ''

  // Extract text from @ to cursor
  const queryText = text.substring(atPosition + 1, cursor)

  return queryText
}

/**
 * Parse current file mention from message and cursor position
 *
 * Combines @ detection and query extraction to provide a complete
 * file mention match. Returns null if no valid mention is detected.
 *
 * @param text - Input text
 * @param cursor - Current cursor position
 * @returns File mention match object, or null if no mention detected
 *
 * @example
 * ```typescript
 * parseCurrentMention("Hello @sample", 13)
 * // { atPosition: 6, query: "sample", cursor: 13 }
 *
 * parseCurrentMention("@", 1)
 * // null (empty query)
 *
 * parseCurrentMention("Hello world", 11)
 * // null (no @ character)
 * ```
 */
export function parseCurrentMention(
  text: string,
  cursor: number
): FileMentionMatch | null {
  const atPosition = findAtSignPosition(text, cursor)
  if (atPosition === -1) return null

  const query = extractQuery(text, cursor, atPosition)

  // No match if query is empty (just typed @)
  if (query === '') return null

  return {
    atPosition,
    query,
    cursor
  }
}

/**
 * Check if cursor is positioned for file mention activation
 *
 * Determines whether the current cursor position and text state
 * should trigger file mention autocomplete. This is true when:
 * - An @ character exists before cursor
 * - Cursor is after the @ character
 * - No whitespace between @ and cursor
 *
 * @param text - Input text
 * @param cursor - Current cursor position
 * @returns True if should activate file mention
 *
 * @example
 * ```typescript
 * shouldActivateMention("@", 1) // true
 * shouldActivateMention("@file", 5) // true
 * shouldActivateMention("@file ", 6) // false (whitespace)
 * shouldActivateMention("Hello", 5) // false (no @)
 * ```
 */
export function shouldActivateMention(text: string, cursor: number): boolean {
  const atPosition = findAtSignPosition(text, cursor)
  return atPosition !== -1 && cursor > atPosition
}

/**
 * Replace file mention with selected file path
 *
 * Replaces the current @ mention query with the selected file path.
 * Maintains cursor position after the replacement.
 *
 * @param text - Original text
 * @param atPosition - Position of @ character
 * @param cursor - Current cursor position
 * @param selectedPath - Selected file path to insert
 * @returns Object with new text and cursor position
 *
 * @example
 * ```typescript
 * replaceMention("Hello @sam", 6, 10, "sample.ts")
 * // { text: "Hello @sample.ts", cursor: 16 }
 *
 * replaceMention("@te", 0, 3, "test.ts")
 * // { text: "@test.ts", cursor: 8 }
 * ```
 */
export function replaceMention(
  text: string,
  atPosition: number,
  cursor: number,
  selectedPath: string
): { text: string; cursor: number } {
  // Replace from @ to cursor with @selectedPath
  const before = text.substring(0, atPosition)
  const after = text.substring(cursor)
  const newText = `${before}@${selectedPath}${after}`
  const newCursor = atPosition + 1 + selectedPath.length

  return { text: newText, cursor: newCursor }
}
