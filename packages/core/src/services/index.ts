/**
 * Services module exports
 *
 * Provides HTTP client and API service layers for toyoura-nagisa.
 * All services are platform-agnostic and can be used in web, CLI, or other frontends.
 */

// HTTP Client
export { HttpClient, apiClient } from './HttpClient';
export type { ApiError } from './HttpClient';

// Chat Service
export { ChatService, chatService } from './ChatService';
export type {
  MessageRequest,
  ChatStreamRequest,
  MessageDeleteRequest,
  MessageDeleteResponse
} from './ChatService';

// Session Service
export { SessionService, sessionService } from './SessionService';
export type {
  CreateSessionRequest,
  CreateSessionResponse,
  SwitchSessionRequest,
  SessionHistoryResponse,
  GenerateTitleRequest,
  GenerateTitleResponse,
  TokenUsageResponse
} from './SessionService';

// Agent Service
export { AgentService, agentService } from './AgentService';

// Tool Service
export { ToolService, toolService } from './ToolService';
export type {
  UpdateToolsEnabledRequest,
  UpdateToolsEnabledResponse,
  UpdateTtsEnabledRequest,
  UpdateTtsEnabledResponse
} from './ToolService';
