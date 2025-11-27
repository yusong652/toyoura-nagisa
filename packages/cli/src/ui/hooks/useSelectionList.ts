/**
 * Selection List Hook
 * Reference: Gemini CLI ui/hooks/useSelectionList.ts (simplified)
 *
 * A headless hook that provides keyboard navigation and selection logic
 * for list-based selection components like radio buttons and menus.
 *
 * Features:
 * - Keyboard navigation with j/k and arrow keys
 * - Selection with Enter key
 * - Numeric quick selection (when showNumbers is true)
 * - Handles disabled items (skips them during navigation)
 * - Wrapping navigation (last to first, first to last)
 */

import { useReducer, useRef, useEffect, useCallback } from 'react';
import { useKeypress, type Key } from './useKeypress.js';

export interface SelectionListItem<T> {
  key: string;
  value: T;
  disabled?: boolean;
}

export interface UseSelectionListOptions<T> {
  items: Array<SelectionListItem<T>>;
  initialIndex?: number;
  onSelect: (value: T) => void;
  onHighlight?: (value: T) => void;
  isFocused?: boolean;
  showNumbers?: boolean;
}

export interface UseSelectionListResult {
  activeIndex: number;
  setActiveIndex: (index: number) => void;
}

interface SelectionListState {
  activeIndex: number;
  pendingHighlight: boolean;
  pendingSelect: boolean;
  itemCount: number;
}

type SelectionListAction =
  | { type: 'SET_ACTIVE_INDEX'; payload: { index: number } }
  | { type: 'MOVE_UP' }
  | { type: 'MOVE_DOWN' }
  | { type: 'SELECT_CURRENT' }
  | { type: 'INITIALIZE'; payload: { itemCount: number; initialIndex: number } }
  | { type: 'CLEAR_PENDING_FLAGS' };

const NUMBER_INPUT_TIMEOUT_MS = 1000;

/**
 * Helper function to find the next index in a given direction, supporting wrapping.
 * Note: This function allows navigation to disabled items (they are visually grayed out
 * but can still be highlighted). Selection of disabled items is prevented in the
 * SELECT_CURRENT action handler.
 */
function findNextValidIndex<T>(
  currentIndex: number,
  direction: 'up' | 'down',
  items: Array<SelectionListItem<T>>
): number {
  const len = items.length;
  if (len === 0) return currentIndex;

  const step = direction === 'down' ? 1 : -1;
  return (currentIndex + step + len) % len;
}

function selectionListReducer(
  state: SelectionListState,
  action: SelectionListAction
): SelectionListState {
  switch (action.type) {
    case 'SET_ACTIVE_INDEX': {
      const { index } = action.payload;
      if (index === state.activeIndex) return state;
      if (index >= 0 && index < state.itemCount) {
        return { ...state, activeIndex: index, pendingHighlight: true };
      }
      return state;
    }

    case 'MOVE_UP': {
      // Actual movement is handled in the hook with items access
      return { ...state, pendingHighlight: true };
    }

    case 'MOVE_DOWN': {
      return { ...state, pendingHighlight: true };
    }

    case 'SELECT_CURRENT': {
      return { ...state, pendingSelect: true };
    }

    case 'INITIALIZE': {
      const { itemCount, initialIndex } = action.payload;
      return {
        ...state,
        itemCount,
        activeIndex: Math.min(initialIndex, Math.max(0, itemCount - 1)),
        pendingHighlight: false,
      };
    }

    case 'CLEAR_PENDING_FLAGS': {
      return { ...state, pendingHighlight: false, pendingSelect: false };
    }

    default:
      return state;
  }
}

/**
 * Check if key matches navigation up (k, up arrow without shift)
 * Note: shift: false ensures Shift+Up is NOT captured, allowing scroll
 */
function isNavigationUp(key: Key): boolean {
  if (key.shift) return false;  // Don't capture Shift+Up
  return key.name === 'up' || key.sequence === 'k';
}

/**
 * Check if key matches navigation down (j, down arrow without shift)
 * Note: shift: false ensures Shift+Down is NOT captured, allowing scroll
 */
function isNavigationDown(key: Key): boolean {
  if (key.shift) return false;  // Don't capture Shift+Down
  return key.name === 'down' || key.sequence === 'j';
}

/**
 * Check if key matches return/enter
 */
function isReturn(key: Key): boolean {
  return key.name === 'return' || key.name === 'enter';
}

export function useSelectionList<T>({
  items,
  initialIndex = 0,
  onSelect,
  onHighlight,
  isFocused = true,
  showNumbers = true,
}: UseSelectionListOptions<T>): UseSelectionListResult {
  const [state, dispatch] = useReducer(selectionListReducer, {
    activeIndex: Math.min(initialIndex, Math.max(0, items.length - 1)),
    pendingHighlight: false,
    pendingSelect: false,
    itemCount: items.length,
  });

  const numberInputRef = useRef('');
  const numberInputTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeIndexRef = useRef(state.activeIndex);

  // Keep ref in sync
  useEffect(() => {
    activeIndexRef.current = state.activeIndex;
  }, [state.activeIndex]);

  // Initialize when items change
  useEffect(() => {
    dispatch({
      type: 'INITIALIZE',
      payload: { itemCount: items.length, initialIndex },
    });
  }, [items.length, initialIndex]);

  // Handle side effects
  useEffect(() => {
    let needsClear = false;

    if (state.pendingHighlight && items[state.activeIndex]) {
      onHighlight?.(items[state.activeIndex]!.value);
      needsClear = true;
    }

    if (state.pendingSelect && items[state.activeIndex]) {
      const currentItem = items[state.activeIndex];
      if (currentItem && !currentItem.disabled) {
        onSelect(currentItem.value);
      }
      needsClear = true;
    }

    if (needsClear) {
      dispatch({ type: 'CLEAR_PENDING_FLAGS' });
    }
  }, [
    state.pendingHighlight,
    state.pendingSelect,
    state.activeIndex,
    items,
    onHighlight,
    onSelect,
  ]);

  // Cleanup timer
  useEffect(() => {
    return () => {
      if (numberInputTimer.current) {
        clearTimeout(numberInputTimer.current);
      }
    };
  }, []);

  const handleKeypress = useCallback(
    (key: Key) => {
      const { sequence } = key;
      const isNumeric = showNumbers && /^[0-9]$/.test(sequence);

      // Clear number input buffer on non-numeric key press
      if (!isNumeric && numberInputTimer.current) {
        clearTimeout(numberInputTimer.current);
        numberInputRef.current = '';
      }

      if (isNavigationUp(key)) {
        const newIndex = findNextValidIndex(activeIndexRef.current, 'up', items);
        if (newIndex !== activeIndexRef.current) {
          dispatch({ type: 'SET_ACTIVE_INDEX', payload: { index: newIndex } });
        }
        return;
      }

      if (isNavigationDown(key)) {
        const newIndex = findNextValidIndex(activeIndexRef.current, 'down', items);
        if (newIndex !== activeIndexRef.current) {
          dispatch({ type: 'SET_ACTIVE_INDEX', payload: { index: newIndex } });
        }
        return;
      }

      if (isReturn(key)) {
        dispatch({ type: 'SELECT_CURRENT' });
        return;
      }

      // Handle numeric input for quick selection
      if (isNumeric) {
        if (numberInputTimer.current) {
          clearTimeout(numberInputTimer.current);
        }

        const newNumberInput = numberInputRef.current + sequence;
        numberInputRef.current = newNumberInput;

        const targetIndex = parseInt(newNumberInput, 10) - 1;

        // Single '0' is invalid (1-indexed)
        if (newNumberInput === '0') {
          numberInputTimer.current = setTimeout(() => {
            numberInputRef.current = '';
          }, NUMBER_INPUT_TIMEOUT_MS);
          return;
        }

        if (targetIndex >= 0 && targetIndex < items.length) {
          dispatch({ type: 'SET_ACTIVE_INDEX', payload: { index: targetIndex } });

          // If the number can't be a prefix for another valid number, select immediately
          const potentialNextNumber = parseInt(newNumberInput + '0', 10);
          if (potentialNextNumber > items.length) {
            dispatch({ type: 'SELECT_CURRENT' });
            numberInputRef.current = '';
          } else {
            numberInputTimer.current = setTimeout(() => {
              dispatch({ type: 'SELECT_CURRENT' });
              numberInputRef.current = '';
            }, NUMBER_INPUT_TIMEOUT_MS);
          }
        } else {
          numberInputRef.current = '';
        }
      }
    },
    [items, showNumbers]
  );

  useKeypress(handleKeypress, { isActive: isFocused && items.length > 0 });

  const setActiveIndex = useCallback((index: number) => {
    dispatch({ type: 'SET_ACTIVE_INDEX', payload: { index } });
  }, []);

  return {
    activeIndex: state.activeIndex,
    setActiveIndex,
  };
}
