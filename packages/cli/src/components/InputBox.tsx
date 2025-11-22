/**
 * InputBox - Text input for sending messages
 */

import React, { useState } from 'react'
import { Box, Text, useInput } from 'ink'

interface InputBoxProps {
  onSend: (text: string) => void
}

const InputBox: React.FC<InputBoxProps> = ({ onSend }) => {
  const [input, setInput] = useState('')

  useInput((inputChar, key) => {
    if (key.return) {
      // Send message on Enter
      if (input.trim()) {
        onSend(input.trim())
        setInput('')
      }
    } else if (key.backspace || key.delete) {
      // Handle backspace
      setInput(input.slice(0, -1))
    } else if (!key.ctrl && !key.meta && inputChar) {
      // Add character to input
      setInput(input + inputChar)
    }
  })

  return (
    <Box borderStyle="single" borderColor="gray" paddingX={1}>
      <Text color="cyan" bold>{'> '}</Text>
      <Text>{input}</Text>
      <Text color="gray">█</Text>
    </Box>
  )
}

export default InputBox
