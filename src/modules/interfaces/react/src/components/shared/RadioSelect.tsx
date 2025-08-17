/**
 * RadioSelect Component
 * 
 * Production-quality radio button selection component
 */

import React, { useState, useEffect, useRef } from 'react';
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

  // Keep activeIndex valid when items or initialIndex prop change
  const prevInitialRef = useRef(initialIndex);
  useEffect(() => {
    // If list is empty, normalize to 0
    if (items.length === 0) {
      if (activeIndex !== 0) setActiveIndex(0);
      prevInitialRef.current = initialIndex;
      return;
    }

    // If initialIndex prop changed, honor it (clamped)
    if (prevInitialRef.current !== initialIndex) {
      const next = Math.max(0, Math.min(initialIndex, items.length - 1));
      setActiveIndex(next);
      prevInitialRef.current = initialIndex;
      return;
    }

    // Otherwise, only ensure current activeIndex remains valid
    let nextIndex = Math.max(0, Math.min(activeIndex, items.length - 1));
    // If current item is disabled, find the next enabled item (wrap once)
    if (items[nextIndex]?.disabled) {
      const len = items.length;
      let found = -1;
      for (let i = 0; i < len; i++) {
        const idx = (nextIndex + i) % len;
        if (!items[idx]?.disabled) { found = idx; break; }
      }
      if (found !== -1) nextIndex = found;
    }
    if (nextIndex !== activeIndex) setActiveIndex(nextIndex);
  }, [items, initialIndex]);

  useInput(
    (input, key) => {
      // Guard empty list or all-disabled list to avoid confusing UX
      const allDisabled = items.length > 0 && items.every(i => i.disabled);
      if (items.length === 0 || allDisabled) {
        return;
      }
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