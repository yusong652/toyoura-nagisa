/**
 * @toyoura-nagisa/core - Shared core logic for web and CLI frontends
 *
 * This package provides platform-agnostic business logic, type definitions,
 * and utilities that can be shared across different frontend implementations.
 *
 * @see https://github.com/yusong652/toyoura-nagisa
 */

export const version = '0.1.0';

// Export all type definitions
export * from './types/index.js';

// Export connection management
export * from './connection/index.js';

// Export services
export * from './services/index.js';

// Export messaging utilities
export * from './messaging/index.js';

// Export session management
export * from './session/index.js';

// Export LLM config service
export * from './services/LlmConfigService.js';

// Export utilities
export * from './utils/index.js';
