/**
 * WebSocket Connection Hook
 * Wraps ConnectionManager from @toyoura-nagisa/core
 */

import { useCallback, useEffect, useRef } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';

export interface UseWebSocketOptions {
  connectionManager: ConnectionManager;
  onStateChange?: (state: string) => void;
  onMessageCreate?: (data: any) => void;
  onStreamingUpdate?: (data: any) => void;
  onToolResultUpdate?: (data: any) => void;
  onToolConfirmation?: (data: any) => void;
  onError?: (error: Error) => void;
}

export interface UseWebSocketReturn {
  connect: () => Promise<void>;
  disconnect: () => void;
  sendMessage: (message: any) => void;
  isConnected: boolean;
}

export function useWebSocket({
  connectionManager,
  onStateChange,
  onMessageCreate,
  onStreamingUpdate,
  onToolResultUpdate,
  onToolConfirmation,
  onError,
}: UseWebSocketOptions): UseWebSocketReturn {
  const isConnectedRef = useRef(false);

  // Set up event listeners
  useEffect(() => {
    const handleStateChange = (state: string) => {
      isConnectedRef.current = state === 'CONNECTED';
      onStateChange?.(state);
    };

    const handleMessage = (data: any) => {
      switch (data.type) {
        case 'MESSAGE_CREATE':
          onMessageCreate?.(data);
          break;
        case 'STREAMING_UPDATE':
          onStreamingUpdate?.(data);
          break;
        case 'TOOL_RESULT_UPDATE':
          onToolResultUpdate?.(data);
          break;
        case 'TOOL_CONFIRMATION_REQUEST':
          onToolConfirmation?.(data);
          break;
        case 'ERROR':
          onError?.(new Error(data.message || 'Unknown error'));
          break;
      }
    };

    const handleError = (error: Error) => {
      onError?.(error);
    };

    connectionManager.on('stateChanged', handleStateChange);
    connectionManager.on('message', handleMessage);
    connectionManager.on('error', handleError);

    return () => {
      connectionManager.off('stateChanged', handleStateChange);
      connectionManager.off('message', handleMessage);
      connectionManager.off('error', handleError);
    };
  }, [connectionManager, onStateChange, onMessageCreate, onStreamingUpdate, onToolResultUpdate, onToolConfirmation, onError]);

  const connect = useCallback(async () => {
    try {
      await connectionManager.connect();
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Connection failed'));
      throw error;
    }
  }, [connectionManager, onError]);

  const disconnect = useCallback(() => {
    connectionManager.disconnect();
    isConnectedRef.current = false;
  }, [connectionManager]);

  const sendMessage = useCallback((message: any) => {
    if (!isConnectedRef.current) {
      console.warn('Cannot send message: not connected');
      return;
    }
    connectionManager.send(message);
  }, [connectionManager]);

  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: isConnectedRef.current,
  };
}
