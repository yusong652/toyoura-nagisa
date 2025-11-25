/**
 * Text filtering utilities for message display.
 *
 * Provides functions to clean and format text content before rendering,
 * including removal of emotion keyword markers.
 *
 * @module @aiNagisa/core/utils/TextFilters
 */

/**
 * Remove emotion keyword markers from text.
 *
 * Filters out [[keyword]] markers that are used for emotion/animation control
 * but should not be displayed to users.
 *
 * @param text - Text content that may contain emotion markers
 * @returns Cleaned text with emotion markers removed
 *
 * @example
 * ```typescript
 * removeEmotionKeywords("Hello [[happy]]") // "Hello"
 * removeEmotionKeywords("Great! [[excited]] Thanks!") // "Great!  Thanks!"
 * ```
 */
export function removeEmotionKeywords(text: string): string {
  if (!text) return text

  // Remove [[keyword]] patterns
  // Preserves surrounding whitespace for natural text flow
  return text.replace(/\[\[[\w\-]+\]\]/g, '').trim()
}

/**
 * Clean text for display.
 *
 * Applies all text cleaning filters including emotion keyword removal
 * and any future text processing requirements.
 *
 * @param text - Raw text content
 * @returns Cleaned text ready for display
 *
 * @example
 * ```typescript
 * cleanTextForDisplay("Hello [[happy]] world") // "Hello  world"
 * ```
 */
export function cleanTextForDisplay(text: string): string {
  if (!text) return text

  let cleaned = text

  // Remove emotion keywords
  cleaned = removeEmotionKeywords(cleaned)

  // Future: Add other text cleaning operations here

  return cleaned
}
