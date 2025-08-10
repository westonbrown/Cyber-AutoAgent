/**
 * RadioSelect Component
 * 
 * Production-quality radio button selection inspired by gemini-cli
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../../themes/theme-manager.js';

export interface RadioSelectItem<T> {
  label: string;
  value: T;
  description?: string;
  disabled?: boolean;
  badge?: string;
}

export interface RadioSelectProps<T> {
  items: Array<RadioSelectItem<T>>;
  initialIndex?: number;
  onSelect: (value: T) => void;
  onHighlight?: (value: T) => void;
  isFocused?: boolean;
  showNumbers?: boolean;
}

export function RadioSelect<T>({
  items,
  initialIndex = 0,
  onSelect,
  onHighlight,
  isFocused = true,
  showNumbers = true,
}: RadioSelectProps<T>): React.JSX.Element {
  const theme = themeManager.getCurrentTheme();
  const [activeIndex, setActiveIndex] = useState(initialIndex);

  useEffect(() => {
    if (onHighlight && items[activeIndex]) {
      onHighlight(items[activeIndex].value);
    }
  }, [activeIndex, items, onHighlight]);

  useInput(
    (input, key) => {
      if (key.upArrow || input === 'k') {
        const newIndex = activeIndex > 0 ? activeIndex - 1 : items.length - 1;
        const item = items[newIndex];
        if (item && !item.disabled) {
          setActiveIndex(newIndex);
        } else {
          // Skip disabled items
          let nextIndex = newIndex;
          while (items[nextIndex]?.disabled) {
            nextIndex = nextIndex > 0 ? nextIndex - 1 : items.length - 1;
            if (nextIndex === newIndex) break; // All items disabled
          }
          if (nextIndex !== newIndex && !items[nextIndex]?.disabled) {
            setActiveIndex(nextIndex);
          }
        }
      }

      if (key.downArrow || input === 'j') {
        const newIndex = activeIndex < items.length - 1 ? activeIndex + 1 : 0;
        const item = items[newIndex];
        if (item && !item.disabled) {
          setActiveIndex(newIndex);
        } else {
          // Skip disabled items
          let nextIndex = newIndex;
          while (items[nextIndex]?.disabled) {
            nextIndex = nextIndex < items.length - 1 ? nextIndex + 1 : 0;
            if (nextIndex === newIndex) break; // All items disabled
          }
          if (nextIndex !== newIndex && !items[nextIndex]?.disabled) {
            setActiveIndex(nextIndex);
          }
        }
      }

      if (key.return) {
        const item = items[activeIndex];
        if (item && !item.disabled) {
          onSelect(item.value);
        }
      }

      // Number selection (1-based)
      if (showNumbers && /^[1-9]$/.test(input)) {
        const index = parseInt(input) - 1;
        if (index >= 0 && index < items.length) {
          const item = items[index];
          if (item && !item.disabled) {
            setActiveIndex(index);
            onSelect(item.value);
          }
        }
      }
    },
    { isActive: isFocused }
  );

  return (
    <Box flexDirection="column">
      {items.map((item, index) => {
        const isSelected = activeIndex === index;
        const isDisabled = item.disabled || false;
        
        let textColor = theme.foreground;
        let bulletColor = theme.muted;
        
        if (isDisabled) {
          textColor = theme.muted;
          bulletColor = theme.muted;
        } else if (isSelected) {
          textColor = theme.primary;
          bulletColor = theme.primary;
        }

        return (
          <Box key={index} marginBottom={1}>
            {/* Radio bullet */}
            <Box minWidth={3} flexShrink={0}>
              <Text color={bulletColor}>
                {isSelected ? '●' : '○'}
              </Text>
            </Box>
            
            {/* Number (if enabled) */}
            {showNumbers && (
              <Box minWidth={4} flexShrink={0}>
                <Text color={isDisabled ? theme.muted : theme.info}>
                  {index + 1}.
                </Text>
              </Box>
            )}
            
            {/* Content */}
            <Box flexDirection="column" flexGrow={1}>
              <Box>
                <Text color={textColor} bold={isSelected}>
                  {item.label}
                </Text>
                {item.badge && (
                  <Text color={isDisabled ? theme.muted : theme.success}> {item.badge}</Text>
                )}
              </Box>
              {item.description && (
                <Box marginLeft={2} marginTop={0.5}>
                  <Text color={theme.muted} dimColor={!isSelected}>
                    {item.description}
                  </Text>
                </Box>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}