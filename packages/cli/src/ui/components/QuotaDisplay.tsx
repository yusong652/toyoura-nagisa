/**
 * Quota Display Component
 *
 * Shows Google Gemini quota usage for Pro and Flash tiers.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { PanelSection } from './shared/PanelSection.js';
import { useKeypress } from '../hooks/useKeypress.js';
import { theme } from '../colors.js';

export interface QuotaWindowInfo {
  label: string;
  used_percent: number;
  remaining_percent: number;
  remaining_fraction: number;
}

interface QuotaDisplayProps {
  title: string;
  accountLabel: string;
  windows: QuotaWindowInfo[];
  isLoading: boolean;
  error: string | null;
  onCancel: () => void;
}

const BAR_WIDTH = 24;

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function getUsageColor(usedPercent: number): string {
  if (usedPercent >= 90) {
    return theme.status.error;
  }
  if (usedPercent >= 75) {
    return theme.status.warning;
  }
  return theme.status.success;
}

function renderBar(usedPercent: number): { filled: string; empty: string } {
  const clamped = clampPercent(usedPercent);
  const filledCount = Math.round((clamped / 100) * BAR_WIDTH);
  const emptyCount = Math.max(0, BAR_WIDTH - filledCount);

  return {
    filled: '#'.repeat(filledCount),
    empty: '-'.repeat(emptyCount),
  };
}

export const QuotaDisplay: React.FC<QuotaDisplayProps> = ({
  title,
  accountLabel,
  windows,
  isLoading,
  error,
  onCancel,
}) => {
  useKeypress(
    (key) => {
      if (key.name === 'escape') {
        onCancel();
      }
    },
    { isActive: true }
  );

  if (isLoading) {
    return (
      <PanelSection
        title={title}
        titlePrefix="?"
        tone="info"
        paddingX={1}
        description={`Account: ${accountLabel}`}
        descriptionColor={theme.text.secondary}
      >
        <Text color={theme.text.muted}>Loading quota...</Text>
      </PanelSection>
    );
  }

  if (error) {
    return (
      <PanelSection
        title={title}
        titlePrefix="!"
        tone="error"
        paddingX={1}
        description={`Account: ${accountLabel}`}
        descriptionColor={theme.text.secondary}
        contentGap={1}
      >
        <Text color={theme.status.error}>{error}</Text>
        <Text color={theme.text.muted}>(Press Esc to close)</Text>
      </PanelSection>
    );
  }

  if (windows.length === 0) {
    return (
      <PanelSection
        title={title}
        titlePrefix="?"
        tone="muted"
        paddingX={1}
        description={`Account: ${accountLabel}`}
        descriptionColor={theme.text.secondary}
        contentGap={1}
      >
        <Text color={theme.text.muted}>No quota data available.</Text>
        <Text color={theme.text.muted}>(Press Esc to close)</Text>
      </PanelSection>
    );
  }

  return (
    <PanelSection
      title={title}
      titlePrefix="?"
      tone="info"
      paddingX={1}
      description={`Account: ${accountLabel}`}
      descriptionColor={theme.text.secondary}
      contentGap={1}
      bodyGap={1}
    >
      {windows.map((window) => {
        const usedPercent = clampPercent(window.used_percent);
        const remainingPercent = clampPercent(window.remaining_percent);
        const { filled, empty } = renderBar(usedPercent);
        const usageColor = getUsageColor(usedPercent);

        return (
          <Box key={window.label} flexDirection="column" gap={0}>
            <Box flexDirection="row" gap={1}>
              <Text color={theme.text.primary}>{window.label.padEnd(6, ' ')}</Text>
              <Text color={usageColor}>{filled}</Text>
              <Text color={theme.text.muted}>{empty}</Text>
            </Box>
            <Text color={theme.text.secondary}>
              {usedPercent.toFixed(0)}% used, {remainingPercent.toFixed(0)}% left
            </Text>
          </Box>
        );
      })}
      <Text color={theme.text.muted}>(Press Esc to close)</Text>
    </PanelSection>
  );
};
