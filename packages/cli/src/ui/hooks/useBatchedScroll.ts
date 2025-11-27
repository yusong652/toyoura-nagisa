/**
 * Batched Scroll Hook
 * Reference: Gemini CLI hooks/useBatchedScroll.ts
 *
 * Manages batched scroll state updates, allowing multiple scroll operations
 * within the same tick to accumulate.
 */

import { useRef, useEffect, useCallback } from 'react';

export function useBatchedScroll(currentScrollTop: number) {
  const pendingScrollTopRef = useRef<number | null>(null);
  const currentScrollTopRef = useRef(currentScrollTop);

  useEffect(() => {
    currentScrollTopRef.current = currentScrollTop;
    pendingScrollTopRef.current = null;
  });

  const getScrollTop = useCallback(
    () => pendingScrollTopRef.current ?? currentScrollTopRef.current,
    [],
  );

  const setPendingScrollTop = useCallback((newScrollTop: number) => {
    pendingScrollTopRef.current = newScrollTop;
  }, []);

  return { getScrollTop, setPendingScrollTop };
}
