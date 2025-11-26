/**
 * Profile Select Dialog Component
 *
 * An interactive dialog for selecting agent profiles.
 * Uses RadioButtonSelect for keyboard navigation and selection.
 */

import React, { useCallback } from 'react';
import { Box, Text } from 'ink';
import { RadioButtonSelect, type RadioSelectItem } from './shared/RadioButtonSelect.js';
import { theme } from '../colors.js';
import { useKeypress } from '../hooks/useKeypress.js';
import type { AgentProfileType } from '../types.js';

// Profile options with descriptions
const PROFILE_OPTIONS: Array<RadioSelectItem<AgentProfileType> & { description: string }> = [
  {
    key: 'coding',
    value: 'coding',
    label: 'Coding',
    description: 'Code development and programming tasks',
  },
  {
    key: 'lifestyle',
    value: 'lifestyle',
    label: 'Lifestyle',
    description: 'Daily life, email, calendar, and communication',
  },
  {
    key: 'pfc',
    value: 'pfc',
    label: 'PFC',
    description: 'ITASCA PFC simulation specialist',
  },
  {
    key: 'general',
    value: 'general',
    label: 'General',
    description: 'Full tool capabilities for complex tasks',
  },
  {
    key: 'disabled',
    value: 'disabled',
    label: 'Disabled',
    description: 'Pure text conversation mode (no tools)',
  },
];

interface ProfileSelectDialogProps {
  /** Current profile */
  currentProfile: AgentProfileType;
  /** Callback when a profile is selected */
  onSelect: (profile: AgentProfileType) => void;
  /** Callback when dialog is cancelled */
  onCancel: () => void;
}

export const ProfileSelectDialog: React.FC<ProfileSelectDialogProps> = ({
  currentProfile,
  onSelect,
  onCancel,
}) => {
  // Find initial index based on current profile
  const initialIndex = PROFILE_OPTIONS.findIndex((p) => p.value === currentProfile);

  // Handle selection
  const handleSelect = useCallback(
    (profile: AgentProfileType) => {
      onSelect(profile);
    },
    [onSelect]
  );

  // Handle escape key to cancel
  useKeypress(
    (key) => {
      if (key.name === 'escape') {
        onCancel();
      }
    },
    { isActive: true }
  );

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.focused}
      paddingX={1}
      paddingY={0}
    >
      {/* Title */}
      <Box marginBottom={1}>
        <Text color={theme.text.accent}>? </Text>
        <Text bold color={theme.text.primary}>
          Select Agent Profile
        </Text>
      </Box>

      {/* Description */}
      <Box marginBottom={1}>
        <Text color={theme.text.secondary}>
          Choose a profile to optimize tool loading for your task:
        </Text>
      </Box>

      {/* Profile list */}
      <RadioButtonSelect
        items={PROFILE_OPTIONS}
        initialIndex={initialIndex >= 0 ? initialIndex : 0}
        onSelect={handleSelect}
        showNumbers={true}
        maxItemsToShow={5}
      />

      {/* Profile descriptions */}
      <Box marginTop={1} flexDirection="column">
        {PROFILE_OPTIONS.map((profile) => (
          <Box key={profile.key}>
            <Text color={theme.text.muted}>
              {profile.label}: {profile.description}
            </Text>
          </Box>
        ))}
      </Box>

      {/* Help text */}
      <Box marginTop={1}>
        <Text color={theme.text.muted}>
          (Use arrows to navigate, Enter to select, Esc to cancel)
        </Text>
      </Box>
    </Box>
  );
};
