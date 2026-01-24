import React, { useEffect, useState } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';
import { useAppState } from '../contexts/AppStateContext.js';

export const NotificationBanner: React.FC = () => {
  const { notification } = useAppState();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (notification) {
      setVisible(true);
    } else {
      setVisible(false);
    }
  }, [notification]);

  if (!notification || !visible) {
    return null;
  }

  const { message, type } = notification;

  let color = theme.text.primary;
  // Unified prefix for all notification types
  const prefix = 'i';

  switch (type) {
    case 'success':
      color = theme.status.success;
      break;
    case 'error':
      color = theme.status.error;
      break;
    case 'info':
    default:
      color = theme.status.info;
      break;
  }

  return (
    <Box paddingX={2} marginBottom={0} flexDirection="row">
      <Text color={color} bold>
        {prefix}
      </Text>
      <Text color={color}> {message}</Text>
    </Box>
  );
};
