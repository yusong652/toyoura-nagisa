import React from 'react';
import { useAgent } from '../contexts/agent/AgentContext';
import { SlideToggle } from './SlideToggle';

export const AgentProfileToggle: React.FC = () => {
  const { toolsEnabled, updateToolsEnabled } = useAgent();

  const handleToggle = async (checked: boolean) => {
    try {
      await updateToolsEnabled(checked);
    } catch (error) {
      console.error('Failed to toggle agent tools:', error);
    }
  };

  return (
    <SlideToggle
      checked={toolsEnabled}
      onChange={handleToggle}
    />
  );
}; 