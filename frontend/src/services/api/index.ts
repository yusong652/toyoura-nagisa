/**
 * API services module exports.
 * 
 * Provides centralized access to all API service instances and types
 * for the aiNagisa frontend application.
 */

// HTTP Client
export { apiClient, HttpClient } from './httpClient'
export type { ApiError } from './httpClient'

// Chat Service
export { chatService, ChatService } from './chatService'
export type {
  MessageRequest,
  ChatStreamRequest,
  MessageDeleteRequest,
  MessageDeleteResponse
} from './chatService'

// Session Service
export { sessionService, SessionService } from './sessionService'
export type {
  CreateSessionRequest,
  CreateSessionResponse,
  SwitchSessionRequest,
  SessionHistoryResponse,
  GenerateTitleRequest,
  GenerateTitleResponse
} from './sessionService'

// Tool Service
export { toolService, ToolService } from './toolService'
export type {
  UpdateToolsEnabledRequest,
  UpdateToolsEnabledResponse,
  UpdateTtsEnabledRequest,
  UpdateTtsEnabledResponse
} from './toolService'

// Agent Service
export { agentService, AgentService } from './agentService'