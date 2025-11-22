/**
 * StatusBar - Display connection status and session info
 */

import React from 'react'
import { Box, Text } from 'ink'
import { ConnectionStatus } from '@aiNagisa/core'

interface StatusBarProps {
  status: ConnectionStatus
  sessionId: string | null
  error: string | null
}

const StatusBar: React.FC<StatusBarProps> = ({ status, sessionId, error }) => {
  const getStatusColor = () => {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        return 'green'
      case ConnectionStatus.CONNECTING:
        return 'yellow'
      case ConnectionStatus.ERROR:
        return 'red'
      default:
        return 'gray'
    }
  }

  const getStatusSymbol = () => {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        return '●'
      case ConnectionStatus.CONNECTING:
        return '◐'
      case ConnectionStatus.ERROR:
        return '✖'
      default:
        return '○'
    }
  }

  return (
    <Box borderStyle="round" borderColor="cyan" paddingX={1}>
      <Text bold color="cyan">aiNagisa CLI</Text>
      <Text> │ </Text>
      <Text color={getStatusColor()}>
        {getStatusSymbol()} {status}
      </Text>
      {sessionId && (
        <>
          <Text> │ </Text>
          <Text dimColor>Session: {sessionId.substring(0, 8)}...</Text>
        </>
      )}
      {error && (
        <>
          <Text> │ </Text>
          <Text color="red">Error: {error}</Text>
        </>
      )}
    </Box>
  )
}

export default StatusBar
