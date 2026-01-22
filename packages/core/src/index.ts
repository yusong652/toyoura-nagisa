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
export * from './types';

// Export connection management
export * from './connection';

// Export services
export * from './services';

// Export messaging utilities
export * from './messaging';

// Export session management
export * from './session';

// Export LLM config service
export * from './services/LlmConfigService';

// Export utilities
export * from './utils';
