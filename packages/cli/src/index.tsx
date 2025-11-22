#!/usr/bin/env node

/**
 * aiNagisa CLI - Command-line interface for aiNagisa AI assistant
 *
 * Usage:
 *   ainagisa                       # Start interactive chat
 *   ainagisa --auto-backend        # Auto-start backend server
 *   ainagisa --session <id>        # Connect to existing session
 *   ainagisa --host <host>         # Custom backend host
 *   ainagisa --port <port>         # Custom backend port
 */

import React from 'react'
import { render } from 'ink'
import ChatApp from './components/ChatApp.js'
import { BackendManager } from './utils/backendManager.js'

// Simple argument parsing (aligned with Gemini CLI / Claude Code approach)
const args = process.argv.slice(2)
const getArg = (name: string, defaultValue?: string): string | undefined => {
  const index = args.findIndex(arg => arg === `--${name}`)
  return index !== -1 && args[index + 1] ? args[index + 1] : defaultValue
}
const hasFlag = (name: string): boolean => args.includes(`--${name}`)

const sessionId = getArg('session')
const host = getArg('host', 'localhost')
const port = parseInt(getArg('port', '8000') || '8000')
const autoBackend = hasFlag('auto-backend')

console.log('🤖 aiNagisa CLI - Starting...\n')

// Check if TTY is available (required for Ink)
if (!process.stdin.isTTY) {
  console.error('❌ Error: Interactive terminal (TTY) required')
  console.error('   Please run this CLI directly in a terminal, not in background mode.')
  console.error('   Example: cd packages/cli && npm run dev')
  process.exit(1)
}

// Main function to handle async backend startup
async function main() {
  let backendManager: BackendManager | null = null

  if (autoBackend) {
    backendManager = new BackendManager(host, port)
    try {
      await backendManager.start()
    } catch (err) {
      console.error(`❌ Failed to start backend: ${err}`)
      process.exit(1)
    }
  }

  // Render Ink app
  const { unmount } = render(
    <ChatApp
      sessionId={sessionId}
      host={host}
      port={port}
    />
  )

  // Cleanup on exit
  const cleanup = () => {
    unmount()
    if (backendManager) {
      backendManager.stop()
    }
  }

  process.on('SIGINT', cleanup)
  process.on('SIGTERM', cleanup)
  process.on('exit', cleanup)
}

// Run main function
main().catch(err => {
  console.error(`❌ Fatal error: ${err}`)
  process.exit(1)
})
