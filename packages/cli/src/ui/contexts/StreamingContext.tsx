/**
 * Streaming Context
 * Provides streaming state to child components
 */

import { createContext, useContext } from 'react';

export enum StreamingState {
  Idle = 'idle',
  Connecting = 'connecting',
  Responding = 'responding',
  WaitingForConfirmation = 'waiting_for_confirmation',
  Error = 'error',
}

export interface StreamingContextValue {
  state: StreamingState;
  currentMessageId: string | null;
  thinkingContent: string | null;
}

const defaultValue: StreamingContextValue = {
  state: StreamingState.Idle,
  currentMessageId: null,
  thinkingContent: null,
};

export const StreamingContext = createContext<StreamingContextValue>(defaultValue);

export function useStreamingState(): StreamingContextValue {
  return useContext(StreamingContext);
}
