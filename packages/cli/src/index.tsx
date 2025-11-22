#!/usr/bin/env node

/**
 * aiNagisa CLI - Command-line interface for aiNagisa AI assistant
 *
 * Usage:
 *   ainagisa                    # Start interactive chat
 *   ainagisa chat               # Start interactive chat
 *   ainagisa --session <id>     # Connect to existing session
 */

import React from 'react'
import { render } from 'ink'
import { Command } from 'commander'
import ChatApp from './components/ChatApp'

const program = new Command()

program
  .name('ainagisa')
  .description('Command-line interface for aiNagisa AI assistant')
  .version('0.1.0')

program
  .command('chat', { isDefault: true })
  .description('Start interactive chat session')
  .option('-s, --session <id>', 'Connect to existing session ID')
  .option('-h, --host <host>', 'Backend server host', 'localhost')
  .option('-p, --port <port>', 'Backend server port', '8000')
  .action((options) => {
    console.log('🤖 aiNagisa CLI - Starting...\n')

    // Render Ink app
    render(
      <ChatApp
        sessionId={options.session}
        host={options.host}
        port={parseInt(options.port)}
      />
    )
  })

program.parse()
