#!/usr/bin/env node

/**
 * aiNagisa CLI - Command-line interface for aiNagisa AI assistant
 *
 * Usage:
 *   ainagisa                    # Start interactive chat
 *   ainagisa --session <id>     # Connect to existing session
 *   ainagisa --host <host>      # Custom backend host
 *   ainagisa --port <port>      # Custom backend port
 *
 * Note: Start backend separately with: npm run start:backend
 */

import React from 'react';
import { render } from 'ink';
import { AppContainer } from './ui/AppContainer.js';
import { defaultConfig, type Config } from './config/settings.js';

// Simple argument parsing
const args = process.argv.slice(2);
const getArg = (name: string, defaultValue?: string): string | undefined => {
  const index = args.findIndex((arg) => arg === `--${name}`);
  return index !== -1 && args[index + 1] ? args[index + 1] : defaultValue;
};

const sessionId = getArg('session');
const host = getArg('host', 'localhost');
const port = parseInt(getArg('port', '8000') || '8000', 10);

// Build config from arguments
const config: Config = {
  ...defaultConfig,
  server: {
    ...defaultConfig.server,
    host: host || defaultConfig.server.host,
    port: port || defaultConfig.server.port,
  },
};

// Clear screen and show startup message
console.clear();
console.log('aiNagisa CLI - Starting...\n');

// Render Ink app
render(<AppContainer config={config} initialSessionId={sessionId} />);
