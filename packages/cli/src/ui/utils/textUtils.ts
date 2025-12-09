/**
 * Unicode-aware text utilities
 * Reference: Gemini CLI ui/utils/textUtils.ts
 *
 * These utilities work at the grapheme cluster level rather than UTF-16
 * code units so that emoji sequences (like ❤️, 👨‍👩‍👧‍👦) and CJK characters
 * are handled correctly as single visual units.
 */

import stringWidth from 'string-width';
import stripAnsi from 'strip-ansi';

// Grapheme segmenter for proper emoji/Unicode handling
// Uses Intl.Segmenter (Node.js 16+) to correctly split strings into
// grapheme clusters, handling:
// - Emoji with variation selectors (❤️ = U+2764 + U+FE0F)
// - ZWJ sequences (👨‍👩‍👧‍👦 = multiple emoji joined with U+200D)
// - Keycap sequences (1️⃣ = digit + U+FE0F + U+20E3)
const graphemeSegmenter = new Intl.Segmenter('en', { granularity: 'grapheme' });

// Cache for grapheme clusters to reduce GC pressure
const graphemesCache = new Map<string, string[]>();
const MAX_STRING_LENGTH_TO_CACHE = 1000;

/**
 * Convert a string to an array of grapheme clusters (handles emoji correctly)
 *
 * Unlike Array.from() which splits by code points, this function uses
 * Intl.Segmenter to split by grapheme clusters, ensuring that multi-codepoint
 * emoji like ❤️ (heart + variation selector) stay together as one unit.
 */
export function toCodePoints(str: string): string[] {
  // ASCII fast path - check if all chars are ASCII (0-127)
  let isAscii = true;
  for (let i = 0; i < str.length; i++) {
    if (str.charCodeAt(i) > 127) {
      isAscii = false;
      break;
    }
  }
  if (isAscii) {
    return str.split('');
  }

  // Cache short strings
  if (str.length <= MAX_STRING_LENGTH_TO_CACHE) {
    const cached = graphemesCache.get(str);
    if (cached) {
      return cached;
    }
  }

  // Use Intl.Segmenter for proper grapheme cluster segmentation
  const result = [...graphemeSegmenter.segment(str)].map(s => s.segment);

  // Cache result
  if (str.length <= MAX_STRING_LENGTH_TO_CACHE) {
    graphemesCache.set(str, result);
  }

  return result;
}

/**
 * Get the code-point length of a string
 */
export function cpLen(str: string): number {
  return toCodePoints(str).length;
}

/**
 * Slice a string by code-point indices
 */
export function cpSlice(str: string, start: number, end?: number): string {
  return toCodePoints(str).slice(start, end).join('');
}

/**
 * Strip characters that can break terminal rendering.
 */
export function stripUnsafeCharacters(str: string): string {
  const strippedAnsi = stripAnsi(str);

  return toCodePoints(strippedAnsi)
    .filter((char) => {
      const code = char.codePointAt(0);
      if (code === undefined) return false;

      // Preserve CR/LF/TAB for line handling
      if (code === 0x0a || code === 0x0d || code === 0x09) return true;

      // Remove C0 control chars (except CR/LF) that can break display
      if (code >= 0x00 && code <= 0x1f) return false;

      // Remove C1 control chars (0x80-0x9f) - legacy 8-bit control codes
      if (code >= 0x80 && code <= 0x9f) return false;

      // Preserve all other characters including Unicode/emojis
      return true;
    })
    .join('');
}

// String width caching for performance optimization
const stringWidthCache = new Map<string, number>();

/**
 * Cached version of stringWidth function for better performance
 */
export function getCachedStringWidth(str: string): number {
  // ASCII printable chars have width 1
  if (/^[\x20-\x7E]*$/.test(str)) {
    return str.length;
  }

  if (stringWidthCache.has(str)) {
    return stringWidthCache.get(str)!;
  }

  const width = stringWidth(str);
  stringWidthCache.set(str, width);

  return width;
}
