import { useState, useCallback, useRef } from 'react';
import { ErrorDisplayConfig } from '../components/UnifiedErrorDisplay';

interface UseErrorDisplayReturn {
  error: ErrorDisplayConfig | null;
  showError: (config: ErrorDisplayConfig | string) => void;
  clearError: () => void;
  showTemporaryError: (message: string, duration?: number) => void;
  showPersistentError: (message: string, actionLabel?: string, onAction?: () => void) => void;
}

/**
 * Hook for managing unified error display state across components.
 * Prevents flickering by managing transition states and provides convenience methods.
 */
export const useErrorDisplay = (): UseErrorDisplayReturn => {
  const [error, setError] = useState<ErrorDisplayConfig | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const clearError = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setError(null);
  }, []);

  const showError = useCallback((config: ErrorDisplayConfig | string) => {
    // Clear any existing timeout to prevent conflicts
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    const errorConfig: ErrorDisplayConfig = typeof config === 'string' 
      ? { message: config }
      : config;

    setError(errorConfig);

    // Auto-hide non-persistent errors
    if (!errorConfig.persistent) {
      const duration = errorConfig.duration || 6000;
      timeoutRef.current = setTimeout(() => {
        clearError();
      }, duration);
    }
  }, [clearError]);

  const showTemporaryError = useCallback((message: string, duration = 4000) => {
    showError({
      message,
      severity: 'error',
      duration,
      position: 'bottom',
      persistent: false
    });
  }, [showError]);

  const showPersistentError = useCallback((
    message: string, 
    actionLabel?: string, 
    onAction?: () => void
  ) => {
    showError({
      message,
      severity: 'error',
      position: 'center',
      persistent: true,
      actionLabel,
      onAction
    });
  }, [showError]);

  return {
    error,
    showError,
    clearError,
    showTemporaryError,
    showPersistentError
  };
};