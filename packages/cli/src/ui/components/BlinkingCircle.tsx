/**
 * Blinking Circle Component
 * Animated indicator for executing/in-progress states
 */

import React from 'react';
import { Text } from 'ink';

interface BlinkingCircleProps {
  color: string;
}

/**
 * Static circle indicator (no animation)
 */
export const BlinkingCircle: React.FC<BlinkingCircleProps> = ({ color }) => {
  return <Text color={color}>○</Text>;
};
