/**
 * ScrollableList Component
 * Reference: Gemini CLI components/shared/ScrollableList.tsx
 *
 * A wrapper around VirtualizedList that provides keyboard scrolling
 * and smooth scroll animations.
 */

import React, {
  useRef,
  forwardRef,
  useImperativeHandle,
  useCallback,
  useEffect,
} from 'react';
import {
  VirtualizedList,
  type VirtualizedListRef,
  SCROLL_TO_ITEM_END,
} from './VirtualizedList.js';
import { Box, type DOMElement } from 'ink';
import { useKeypress, type Key } from '../../hooks/useKeypress.js';

const ANIMATION_FRAME_DURATION_MS = 33;
const SCROLL_LINE_HEIGHT = 3; // Scroll 3 lines at a time

type VirtualizedListProps<T> = {
  data: T[];
  renderItem: (info: { item: T; index: number }) => React.ReactElement;
  estimatedItemHeight: (index: number) => number;
  keyExtractor: (item: T, index: number) => string;
  initialScrollIndex?: number;
  initialScrollOffsetInIndex?: number;
};

interface ScrollableListProps<T> extends VirtualizedListProps<T> {
  hasFocus: boolean;
}

export type ScrollableListRef<T> = VirtualizedListRef<T>;

function ScrollableList<T>(
  props: ScrollableListProps<T>,
  ref: React.Ref<ScrollableListRef<T>>,
) {
  const { hasFocus } = props;
  const virtualizedListRef = useRef<VirtualizedListRef<T>>(null);
  const containerRef = useRef<DOMElement>(null);

  useImperativeHandle(
    ref,
    () => ({
      scrollBy: (delta) => virtualizedListRef.current?.scrollBy(delta),
      scrollTo: (offset) => virtualizedListRef.current?.scrollTo(offset),
      scrollToEnd: () => virtualizedListRef.current?.scrollToEnd(),
      scrollToIndex: (params) =>
        virtualizedListRef.current?.scrollToIndex(params),
      scrollToItem: (params) =>
        virtualizedListRef.current?.scrollToItem(params),
      getScrollIndex: () => virtualizedListRef.current?.getScrollIndex() ?? 0,
      getScrollState: () =>
        virtualizedListRef.current?.getScrollState() ?? {
          scrollTop: 0,
          scrollHeight: 0,
          innerHeight: 0,
        },
    }),
    [],
  );

  const getScrollState = useCallback(
    () =>
      virtualizedListRef.current?.getScrollState() ?? {
        scrollTop: 0,
        scrollHeight: 0,
        innerHeight: 0,
      },
    [],
  );

  const scrollBy = useCallback((delta: number) => {
    virtualizedListRef.current?.scrollBy(delta);
  }, []);

  // Smooth scroll state
  const smoothScrollState = useRef<{
    active: boolean;
    start: number;
    from: number;
    to: number;
    duration: number;
    timer: NodeJS.Timeout | null;
  }>({ active: false, start: 0, from: 0, to: 0, duration: 0, timer: null });

  const stopSmoothScroll = useCallback(() => {
    if (smoothScrollState.current.timer) {
      clearInterval(smoothScrollState.current.timer);
      smoothScrollState.current.timer = null;
    }
    smoothScrollState.current.active = false;
  }, []);

  useEffect(() => stopSmoothScroll, [stopSmoothScroll]);

  const smoothScrollTo = useCallback(
    (targetScrollTop: number, duration: number = 200) => {
      stopSmoothScroll();

      const scrollState = virtualizedListRef.current?.getScrollState() ?? {
        scrollTop: 0,
        scrollHeight: 0,
        innerHeight: 0,
      };
      const {
        scrollTop: startScrollTop,
        scrollHeight,
        innerHeight,
      } = scrollState;

      const maxScrollTop = Math.max(0, scrollHeight - innerHeight);

      let effectiveTarget = targetScrollTop;
      if (targetScrollTop === SCROLL_TO_ITEM_END) {
        effectiveTarget = maxScrollTop;
      }

      const clampedTarget = Math.max(
        0,
        Math.min(maxScrollTop, effectiveTarget),
      );

      if (duration === 0) {
        if (targetScrollTop === SCROLL_TO_ITEM_END) {
          virtualizedListRef.current?.scrollTo(SCROLL_TO_ITEM_END);
        } else {
          virtualizedListRef.current?.scrollTo(Math.round(clampedTarget));
        }
        return;
      }

      smoothScrollState.current = {
        active: true,
        start: Date.now(),
        from: startScrollTop,
        to: clampedTarget,
        duration,
        timer: setInterval(() => {
          const now = Date.now();
          const elapsed = now - smoothScrollState.current.start;
          const progress = Math.min(elapsed / duration, 1);

          // Ease-in-out
          const t = progress;
          const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

          const current =
            smoothScrollState.current.from +
            (smoothScrollState.current.to - smoothScrollState.current.from) *
              ease;

          if (progress >= 1) {
            if (targetScrollTop === SCROLL_TO_ITEM_END) {
              virtualizedListRef.current?.scrollTo(SCROLL_TO_ITEM_END);
            } else {
              virtualizedListRef.current?.scrollTo(Math.round(current));
            }
            stopSmoothScroll();
          } else {
            virtualizedListRef.current?.scrollTo(Math.round(current));
          }
        }, ANIMATION_FRAME_DURATION_MS),
      };
    },
    [stopSmoothScroll],
  );

  // Keyboard scrolling
  // Use Shift+Up/Down to avoid conflict with input cursor navigation
  useKeypress(
    (key: Key) => {
      // Shift+Up arrow - scroll up (avoids conflict with input cursor movement)
      if (key.name === 'up' && key.shift) {
        stopSmoothScroll();
        scrollBy(-SCROLL_LINE_HEIGHT);
      }
      // Shift+Down arrow - scroll down (avoids conflict with input cursor movement)
      else if (key.name === 'down' && key.shift) {
        stopSmoothScroll();
        scrollBy(SCROLL_LINE_HEIGHT);
      }
      // Page Up
      else if (key.name === 'pageup') {
        const scrollState = getScrollState();
        const current = smoothScrollState.current.active
          ? smoothScrollState.current.to
          : scrollState.scrollTop;
        const innerHeight = scrollState.innerHeight;
        smoothScrollTo(current - innerHeight);
      }
      // Page Down
      else if (key.name === 'pagedown') {
        const scrollState = getScrollState();
        const current = smoothScrollState.current.active
          ? smoothScrollState.current.to
          : scrollState.scrollTop;
        const innerHeight = scrollState.innerHeight;
        smoothScrollTo(current + innerHeight);
      }
      // Home - scroll to top
      else if (key.name === 'home') {
        smoothScrollTo(0);
      }
      // End - scroll to bottom
      else if (key.name === 'end') {
        smoothScrollTo(SCROLL_TO_ITEM_END);
      }
    },
    { isActive: hasFocus },
  );

  return (
    <Box
      ref={containerRef}
      flexGrow={1}
      flexDirection="column"
      overflow="hidden"
    >
      <VirtualizedList ref={virtualizedListRef} {...props} />
    </Box>
  );
}

const ScrollableListWithForwardRef = forwardRef(ScrollableList) as <T>(
  props: ScrollableListProps<T> & { ref?: React.Ref<ScrollableListRef<T>> },
) => React.ReactElement;

export { ScrollableListWithForwardRef as ScrollableList, SCROLL_TO_ITEM_END };
