/**
 * Radio Button Select Component
 * Reference: Gemini CLI ui/components/shared/RadioButtonSelect.tsx (simplified)
 *
 * A component that displays a list of items with radio buttons,
 * supporting keyboard navigation with up/down arrows and number keys.
 */

import React, { useEffect, useState } from 'react';
import { Box, Text, type TextProps } from 'ink';
import { useSelectionList, type SelectionListItem } from '../../hooks/useSelectionList.js';
import { theme, colors } from '../../colors.js';

// Color type for Text component
type TextColor = TextProps['color'];

/**
 * Represents a single option for the RadioButtonSelect.
 */
export interface RadioSelectItem<T> extends SelectionListItem<T> {
  label: string;
}

export interface RadioButtonSelectProps<T> {
  /** An array of items to display as radio options. */
  items: Array<RadioSelectItem<T>>;
  /** The initial index selected */
  initialIndex?: number;
  /** Function called when an item is selected. Receives the `value` of the selected item. */
  onSelect: (value: T) => void;
  /** Function called when an item is highlighted. Receives the `value` of the selected item. */
  onHighlight?: (value: T) => void;
  /** Whether this select input is currently focused and should respond to input. */
  isFocused?: boolean;
  /** Whether to show the scroll arrows. */
  showScrollArrows?: boolean;
  /** The maximum number of items to show at once. */
  maxItemsToShow?: number;
  /** Whether to show numbers next to items. */
  showNumbers?: boolean;
}

/**
 * A custom component that displays a list of items with radio buttons,
 * supporting scrolling and keyboard navigation.
 */
export function RadioButtonSelect<T>({
  items,
  initialIndex = 0,
  onSelect,
  onHighlight,
  isFocused = true,
  showScrollArrows = false,
  maxItemsToShow = 10,
  showNumbers = true,
}: RadioButtonSelectProps<T>): React.JSX.Element {
  const { activeIndex } = useSelectionList({
    items,
    initialIndex,
    onSelect,
    onHighlight,
    isFocused,
    showNumbers,
  });

  const [scrollOffset, setScrollOffset] = useState(0);

  // Handle scrolling for long lists
  useEffect(() => {
    const newScrollOffset = Math.max(
      0,
      Math.min(activeIndex - maxItemsToShow + 1, items.length - maxItemsToShow)
    );
    if (activeIndex < scrollOffset) {
      setScrollOffset(activeIndex);
    } else if (activeIndex >= scrollOffset + maxItemsToShow) {
      setScrollOffset(newScrollOffset);
    }
  }, [activeIndex, items.length, scrollOffset, maxItemsToShow]);

  const visibleItems = items.slice(scrollOffset, scrollOffset + maxItemsToShow);
  const numberColumnWidth = String(items.length).length;
  const selectedBackground = colors.primary;
  const selectedTextColor: TextColor = colors.bg;

  return (
    <Box flexDirection="column">
      {/* Up scroll indicator */}
      {showScrollArrows && (
        <Text color={scrollOffset > 0 ? theme.text.primary : theme.text.muted}>
          {scrollOffset > 0 ? '▲' : ' '}
        </Text>
      )}

      {visibleItems.map((item, index) => {
        const itemIndex = scrollOffset + index;
        const isSelected = activeIndex === itemIndex;
        const rowBackgroundColor = isSelected ? selectedBackground : undefined;

        // Determine colors based on selection and disabled state
        let titleColor: TextColor = theme.text.primary;
        let numberColor: TextColor = theme.text.primary;

        if (isSelected) {
          titleColor = selectedTextColor;
          numberColor = selectedTextColor;
        } else if (item.disabled) {
          titleColor = theme.text.muted;
          numberColor = theme.text.muted;
        }

        if (!isFocused && !item.disabled && !isSelected) {
          numberColor = theme.text.muted;
        }

        if (!showNumbers) {
          numberColor = theme.text.muted;
        }

        const itemNumberText = `${String(itemIndex + 1).padStart(numberColumnWidth)}.`;

        return (
          <Box key={item.key} alignItems="flex-start" backgroundColor={rowBackgroundColor}>
            {/* Radio button indicator */}
            <Box minWidth={2} flexShrink={0}>
              <Text color={isSelected ? selectedTextColor : theme.text.primary}>
                {isSelected ? '●' : ' '}
              </Text>
            </Box>

            {/* Item number */}
            {showNumbers && (
              <Box marginRight={1} flexShrink={0} minWidth={itemNumberText.length}>
                <Text color={numberColor}>{itemNumberText}</Text>
              </Box>
            )}

            {/* Item label */}
            <Box flexGrow={1}>
              <Text color={titleColor} wrap="truncate">
                {item.label}
              </Text>
            </Box>
          </Box>
        );
      })}

      {/* Down scroll indicator */}
      {showScrollArrows && (
        <Text
          color={
            scrollOffset + maxItemsToShow < items.length
              ? theme.text.primary
              : theme.text.muted
          }
        >
          {scrollOffset + maxItemsToShow < items.length ? '▼' : ' '}
        </Text>
      )}
    </Box>
  );
}
