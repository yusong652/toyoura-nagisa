/**
 * Utils module - Common utilities
 *
 * This module provides utility classes and functions used across the core package.
 */

export { EventEmitter } from './EventEmitter.js';

// Text processing utilities
export {
  removeEmotionKeywords,
  cleanTextForDisplay
} from './TextFilters.js';

// Time formatting utilities
export {
  getRelativeTime,
  getAbsoluteTime,
  formatSmartTime,
  type TimeDisplayOptions
} from './TimeFormatter.js';

// File mention parsing utilities
export {
  findAtSignPosition,
  extractQuery,
  parseCurrentMention,
  shouldActivateMention,
  replaceMention,
  type FileMentionMatch
} from './FileMentionParser.js';
