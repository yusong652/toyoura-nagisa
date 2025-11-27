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
import { KeypressProvider } from './ui/contexts/KeypressContext.js';
import { MouseProvider } from './ui/contexts/MouseContext.js';
import { ScrollProvider } from './ui/contexts/ScrollProvider.js';
import { defaultConfig, type Config } from './config/settings.js';
import { themeManager } from './ui/themes/index.js';

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

// Initialize theme from saved config
themeManager.initialize();

// Render Ink app with full provider hierarchy for proper event handling
// Order: Keypress -> Mouse -> Scroll -> App
// Using alternateBuffer mode for better resize handling and mouse support
render(
  <KeypressProvider>
    <MouseProvider mouseEventsEnabled={true}>
      <ScrollProvider>
        <AppContainer config={config} initialSessionId={sessionId} />
      </ScrollProvider>
    </MouseProvider>
  </KeypressProvider>,
  {
    exitOnCtrlC: false,
    // Alternate buffer mode: Ink manages a separate screen buffer
    // This eliminates flickering during resize as Ink handles re-rendering automatically
    alternateBuffer: true,
    // Enable incremental rendering for better performance
    // Only re-renders changed regions instead of full screen
    incrementalRendering: true,
  }
);
