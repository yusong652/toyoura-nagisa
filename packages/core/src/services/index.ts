/**
 * Services module exports
 *
 * Provides HTTP client and API service layers for toyoura-nagisa.
 * All services are platform-agnostic and can be used in web, CLI, or other frontends.
 */

// HTTP Client
export { HttpClient, apiClient } from './HttpClient.js';
export type { ApiError } from './HttpClient.js';

// Chat Service
export { ChatService, chatService } from './ChatService.js';
export type {
  MessageRequest,
  ChatStreamRequest,
  MessageDeleteRequest,
  MessageDeleteData
} from './ChatService.js';

// Session Service
export { SessionService, sessionService } from './SessionService.js';
export type {
  CreateSessionRequest,
  CreateSessionResponse,
  SwitchSessionRequest,
  SessionHistoryResponse,
  GenerateTitleRequest,
  GenerateTitleData,
  TokenUsageResponse,
  UpdateSessionModeRequest,
  UpdateSessionModeResponse,
} from './SessionService.js';

// LLM Config Service
export { LlmConfigService, llmConfigService } from './LlmConfigService.js';
export type {
  ModelDetails,
  ProviderInfo,
  ProviderListResponse,
  LlmConfigUpdateData,
} from './LlmConfigService.js';
