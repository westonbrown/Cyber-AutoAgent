/**
 * Virtualized Output Component
 * 
 * Optimizes rendering of large output streams by only rendering visible items.
 * Inspired by performance patterns from reference CLIs.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Box, Text, useApp } from 'ink';

interface OutputItem {
  id: string;
  content: string;
  type: 'info' | 'error' | 'warning' | 'success' | 'tool';
  timestamp: Date;
}

interface VirtualizedOutputProps {
  items: OutputItem[];
  height?: number;
  showTimestamps?: boolean;
  filterType?: string;
}

export const VirtualizedOutput: React.FC<VirtualizedOutputProps> = ({
  items,
  height = 20,
  showTimestamps = false,
  filterType
}) => {
  const [scrollOffset, setScrollOffset] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<number>(0);

  // Filter items if needed
  const filteredItems = useMemo(() => {
    if (!filterType) return items;
    return items.filter(item => item.type === filterType);
  }, [items, filterType]);

  // Calculate visible range
  const visibleItems = useMemo(() => {
    const startIndex = Math.max(0, filteredItems.length - height - scrollOffset);
    const endIndex = Math.min(filteredItems.length, startIndex + height);
    return filteredItems.slice(startIndex, endIndex);
  }, [filteredItems, height, scrollOffset]);

  // Auto-scroll to bottom when new items arrive
  useEffect(() => {
    if (autoScroll && items.length > containerRef.current) {
      setScrollOffset(0);
    }
    containerRef.current = items.length;
  }, [items.length, autoScroll]);

  // Color mapping for different types
  const getColor = (type: OutputItem['type']) => {
    switch (type) {
      case 'error': return 'red';
      case 'warning': return 'yellow';
      case 'success': return 'green';
      case 'tool': return 'magenta';
      default: return 'white';
    }
  };

  // Format timestamp
  const formatTimestamp = (date: Date) => {
    return date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <Box flexDirection="column" height={height}>
      {/* Scroll indicator */}
      {scrollOffset > 0 && (
        <Box marginBottom={1}>
          <Text dimColor>
            ↑ {scrollOffset} more items above
          </Text>
        </Box>
      )}

      {/* Output items */}
      {visibleItems.map((item) => (
        <Box key={item.id} marginBottom={0}>
          {showTimestamps && (
            <Text dimColor>
              [{formatTimestamp(item.timestamp)}] 
            </Text>
          )}
          <Text color={getColor(item.type)}>
            {item.content}
          </Text>
        </Box>
      ))}

      {/* Bottom indicator */}
      {filteredItems.length > height + scrollOffset && (
        <Box marginTop={1}>
          <Text dimColor>
            ↓ {filteredItems.length - height - scrollOffset} more items below
          </Text>
        </Box>
      )}

      {/* Status bar */}
      <Box marginTop={1} borderStyle="single" borderColor="gray">
        <Text dimColor>
          {autoScroll ? '🔄 Auto-scroll ON' : '⏸ Auto-scroll OFF'} | 
          Showing {visibleItems.length}/{filteredItems.length} items
        </Text>
      </Box>
    </Box>
  );
};

// Hook for converting operation history to VirtualizedOutput format
export const useVirtualizedHistory = (operationHistory: any[]) => {
  return React.useMemo(() => {
    return operationHistory.map((entry, index) => ({
      id: entry.id || `item-${index}`,
      content: entry.content,
      type: entry.type as 'info' | 'error' | 'warning' | 'success' | 'tool',
      timestamp: entry.timestamp || new Date()
    }));
  }, [operationHistory]);
};

export default VirtualizedOutput;