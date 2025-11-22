/**
 * ChatApp - Main CLI application component
 * Uses @aiNagisa/core for WebSocket and message management
 */

import React, { useState, useEffect } from 'react'
import { Box, Text } from 'ink'
import { WebSocketManager, ConnectionStatus, MessageManager } from '@aiNagisa/core'
import type { Message } from '@aiNagisa/core'
import MessageList from './MessageList'
import InputBox from './InputBox'
import StatusBar from './StatusBar'

interface ChatAppProps {
  sessionId?: string
  host?: string
  port?: number
}

const ChatApp: React.FC<ChatAppProps> = ({
  sessionId: providedSessionId,
  host = 'localhost',
  port = 8000
}) => {
  const [wsManager] = useState(() => new WebSocketManager(host, port))
  const [messageManager] = useState(() => new MessageManager())
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Initialize WebSocket connection
  useEffect(() => {
    // Subscribe to message changes
    const unsubscribe = messageManager.subscribe((messages) => {
      setMessages(messages)
    })

    // Setup WebSocket event handlers
    wsManager.on('statusChange', (newStatus: ConnectionStatus) => {
      setStatus(newStatus)
    })

    wsManager.on('error', (err: Error) => {
      setError(err.message)
    })

    wsManager.on('MESSAGE_CREATE', (data: any) => {
      // Create placeholder message
      messageManager.createMessage(
        data.message_id,
        data.role,
        data.initial_text ? [{ type: 'text', text: data.initial_text }] : []
      )
    })

    wsManager.on('STREAMING_UPDATE', (data: any) => {
      // Update message content during streaming
      messageManager.updateMessage(
        data.message_id,
        data.content,
        data.streaming
      )

      if (!data.streaming) {
        messageManager.finalizeMessage(data.message_id)
      }
    })

    wsManager.on('MESSAGE_SAVED', (data: any) => {
      // Message saved to backend, finalize it
      if (data.message_id) {
        messageManager.finalizeMessage(data.message_id)
      }
    })

    // Connect to session
    const initSession = async () => {
      let sid = providedSessionId

      if (!sid) {
        // Create new session via API
        try {
          const response = await fetch(`http://${host}:${port}/api/history/create`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              profile: 'general',
              enable_memory: true
            })
          })
          const data = await response.json()
          sid = data.session_id
        } catch (err) {
          setError('Failed to create session')
          return
        }
      }

      setSessionId(sid)

      try {
        await wsManager.connect(sid)
      } catch (err) {
        setError(`Failed to connect: ${err}`)
      }
    }

    initSession()

    // Cleanup
    return () => {
      unsubscribe()
      wsManager.disconnect()
      wsManager.removeAllListeners()
    }
  }, [wsManager, messageManager, providedSessionId, host, port])

  // Send message handler
  const handleSendMessage = (text: string) => {
    if (!sessionId) {
      setError('Not connected to session')
      return
    }

    // Create user message locally
    const userMessageId = `user-${Date.now()}`
    messageManager.createMessage(userMessageId, 'user', [{ type: 'text', text }])

    // Send to backend via WebSocket (using same protocol as Web frontend)
    wsManager.send({
      type: 'CHAT_MESSAGE',           // ← Changed from USER_MESSAGE
      session_id: sessionId,
      message_id: userMessageId,
      message: text,                  // ← Changed from 'text' to 'message'
      agent_profile: 'general',       // ← Added
      enable_memory: true,            // ← Added
      tts_enabled: false,             // ← Added (CLI doesn't support TTS yet)
      files: [],
      mentioned_files: [],
      stream_response: true,          // ← Added
      timestamp: new Date().toISOString()
    })
  }

  return (
    <Box flexDirection="column" height="100%">
      <StatusBar status={status} sessionId={sessionId} error={error} />

      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        {status === ConnectionStatus.CONNECTED ? (
          <>
            <MessageList messages={messages} />
            <InputBox onSend={handleSendMessage} />
          </>
        ) : (
          <Box flexDirection="column" alignItems="center" justifyContent="center" flexGrow={1}>
            <Text color="yellow">
              {status === ConnectionStatus.CONNECTING && '⏳ Connecting...'}
              {status === ConnectionStatus.DISCONNECTED && '❌ Disconnected'}
              {status === ConnectionStatus.ERROR && `❌ Error: ${error}`}
            </Text>
          </Box>
        )}
      </Box>
    </Box>
  )
}

export default ChatApp
