/**
 * Terminal Size Context
 * Provides terminal dimensions to all components via context.
 * Uses a single resize listener to avoid EventEmitter memory leaks.
 */

import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

interface TerminalSize {
  columns: number;
  rows: number;
}

const TerminalSizeContext = createContext<TerminalSize>({
  columns: 80,
  rows: 24,
});

interface TerminalSizeProviderProps {
  children: ReactNode;
}

export function TerminalSizeProvider({ children }: TerminalSizeProviderProps): React.ReactElement {
  const [size, setSize] = useState<TerminalSize>({
    columns: process.stdout.columns || 80,
    rows: process.stdout.rows || 24,
  });

  useEffect(() => {
    function updateSize() {
      setSize({
        columns: process.stdout.columns || 80,
        rows: process.stdout.rows || 24,
      });
    }

    process.stdout.on('resize', updateSize);
    return () => {
      process.stdout.off('resize', updateSize);
    };
  }, []);

  return (
    <TerminalSizeContext.Provider value={size}>
      {children}
    </TerminalSizeContext.Provider>
  );
}

/**
 * Hook to get current terminal size.
 * Must be used within a TerminalSizeProvider.
 */
export function useTerminalSize(): TerminalSize {
  return useContext(TerminalSizeContext);
}
