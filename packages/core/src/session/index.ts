/**
 * Session module - Session lifecycle management
 *
 * This module provides platform-agnostic session management including
 * CRUD operations, current session tracking, and token usage monitoring.
 */

// Session manager
export {
  SessionManager,
  StorageAdapter,
  SessionEvent,
  SessionCreatedPayload,
  SessionSwitchedPayload,
  SessionDeletedPayload,
  SessionsLoadedPayload,
  TitleUpdatedPayload,
  TokenUsageUpdatedPayload
} from './SessionManager.js';

// Storage adapters
export { LocalStorageAdapter } from './adapters/LocalStorageAdapter.js';
export { FileStorageAdapter } from './adapters/FileStorageAdapter.js';
