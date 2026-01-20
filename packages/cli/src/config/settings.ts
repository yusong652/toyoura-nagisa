/**
 * CLI Configuration Settings
 */

import { z } from 'zod';

// Configuration schema
export const configSchema = z.object({
  // Server connection
  server: z.object({
    host: z.string().default('localhost'),
    port: z.number().default(8000),
    secure: z.boolean().default(false),
  }).default({}),

  // Session settings
  session: z.object({
    autoRestore: z.boolean().default(true),
    historyLimit: z.number().default(100),
  }).default({}),

  // UI settings
  ui: z.object({
    showThinking: z.boolean().default(true),
    showToolCalls: z.boolean().default(true),
    compactMode: z.boolean().default(false),
  }).default({}),

  // Agent profile
  agent: z.object({
    defaultProfile: z.string().default('pfc_expert'),
  }).default({}),
});

export type Config = z.infer<typeof configSchema>;

// Default configuration
export const defaultConfig: Config = configSchema.parse({});

// Get WebSocket URL from config
export function getWebSocketUrl(config: Config, sessionId: string): string {
  const protocol = config.server.secure ? 'wss' : 'ws';
  return `${protocol}://${config.server.host}:${config.server.port}/ws/${sessionId}`;
}

// Get API base URL from config
export function getApiBaseUrl(config: Config): string {
  const protocol = config.server.secure ? 'https' : 'http';
  return `${protocol}://${config.server.host}:${config.server.port}`;
}
