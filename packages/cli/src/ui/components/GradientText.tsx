/**
 * Gradient Text Component
 * Reference: Gemini CLI ui/components/ThemedGradient.tsx
 *
 * Renders text with gradient colors based on theme
 */

import React from 'react';
import { Text, type TextProps } from 'ink';
import Gradient from 'ink-gradient';
import { theme } from '../colors.js';

interface GradientTextProps extends TextProps {
  children: React.ReactNode;
  /** Custom gradient colors (overrides theme) */
  colors?: string[];
}

export const GradientText: React.FC<GradientTextProps> = ({
  children,
  colors,
  ...props
}) => {
  // Use custom colors or theme gradient
  const gradientColors = colors || theme.gradient;

  if (gradientColors && gradientColors.length >= 2) {
    return (
      <Gradient colors={gradientColors}>
        <Text {...props}>{children}</Text>
      </Gradient>
    );
  }

  if (gradientColors && gradientColors.length === 1) {
    return (
      <Text color={gradientColors[0]} {...props}>
        {children}
      </Text>
    );
  }

  // Fallback to accent color if no gradient
  return (
    <Text color={theme.text.accent} {...props}>
      {children}
    </Text>
  );
};
