/**
 * Blinking Circle Component
 * Animated indicator for executing/in-progress states
 */

import React, { useState, useEffect } from 'react';
import { Text } from 'ink';

interface BlinkingCircleProps {
  color: string;
}

/**
 * Blinking circle indicator that alternates between filled and empty circle
 */
export const BlinkingCircle: React.FC<BlinkingCircleProps> = ({ color }) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible((v) => !v);
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return <Text color={color}>{visible ? '●' : '○'}</Text>;
};
