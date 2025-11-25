/**
 * Streaming Context
 * Provides streaming state to child components
 * Reference: Gemini CLI ui/contexts/StreamingContext.tsx
 */

import React, { createContext } from 'react';

export enum StreamingState {
  Idle = 'idle',
  Connecting = 'connecting',
  Responding = 'responding',
  WaitingForConfirmation = 'waiting_for_confirmation',
  Error = 'error',
}

export const StreamingContext = createContext<StreamingState | undefined>(
  undefined,
);

export const useStreamingContext = (): StreamingState => {
  const context = React.useContext(StreamingContext);
  if (context === undefined) {
    throw new Error(
      'useStreamingContext must be used within a StreamingContext.Provider',
    );
  }
  return context;
};
