#!/usr/bin/env node

/**
 * aiNagisa CLI - Command-line interface for aiNagisa AI assistant
 *
 * Usage:
 *   ainagisa                    # Start interactive chat
 *   ainagisa --session <id>     # Connect to existing session
 *   ainagisa --host <host>      # Custom backend host
 *   ainagisa --port <port>      # Custom backend port
 */

import React from 'react'
import { render } from 'ink'
import ChatApp from './components/ChatApp.js'

// Simple argument parsing (aligned with Gemini CLI / Claude Code approach)
const args = process.argv.slice(2)
const getArg = (name: string, defaultValue?: string): string | undefined => {
  const index = args.findIndex(arg => arg === `--${name}`)
  return index !== -1 && args[index + 1] ? args[index + 1] : defaultValue
}

const sessionId = getArg('session')
const host = getArg('host', 'localhost')
const port = parseInt(getArg('port', '8000') || '8000')

console.log('🤖 aiNagisa CLI - Starting...\n')

// Check if TTY is available (required for Ink)
if (!process.stdin.isTTY) {
  console.error('❌ Error: Interactive terminal (TTY) required')
  console.error('   Please run this CLI directly in a terminal, not in background mode.')
  console.error('   Example: cd packages/cli && npm run dev')
  process.exit(1)
}

// Render Ink app
render(
  <ChatApp
    sessionId={sessionId}
    host={host}
    port={port}
  />
)
