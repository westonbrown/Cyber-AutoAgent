/**
 * Optimized Static Component
 * 
 * Fixes the duplicate rendering issues found in test captures.
 * Properly manages static content to prevent re-renders.
 */

import React, { useMemo, useRef, useEffect } from 'react';
import { Box, Static } from 'ink';

interface OptimizedStaticProps {
  items: Array<{ id: string; content: React.ReactNode }>;
  keyPrefix?: string;
  shouldUpdate?: boolean;
}

export const OptimizedStatic: React.FC<OptimizedStaticProps> = React.memo(({
  items,
  keyPrefix = 'static',
  shouldUpdate = false
}) => {
  const previousItemsRef = useRef<string[]>([]);
  
  // Only update if items actually changed
  const itemKeys = useMemo(() => {
    const keys = items.map(item => `${keyPrefix}_${item.id}`);
    
    // Check if items actually changed
    const changed = keys.length !== previousItemsRef.current.length ||
      keys.some((key, index) => key !== previousItemsRef.current[index]);
    
    if (changed || shouldUpdate) {
      previousItemsRef.current = keys;
      return keys;
    }
    
    return previousItemsRef.current;
  }, [items, keyPrefix, shouldUpdate]);
  
  // Create item map for fast lookup
  const itemMap = useMemo(() => {
    const map = new Map<string, React.ReactNode>();
    items.forEach(item => {
      map.set(`${keyPrefix}_${item.id}`, item.content);
    });
    return map;
  }, [items, keyPrefix]);
  
  // Prevent re-render if nothing changed
  if (itemKeys.length === 0) {
    return null;
  }
  
  return (
    <Static items={itemKeys}>
      {(key: string) => {
        const content = itemMap.get(key);
        if (!content) return <Box key={key} />;
        
        return (
          <Box key={key}>
            {content}
          </Box>
        );
      }}
    </Static>
  );
}, (prevProps, nextProps) => {
  // Custom comparison to prevent unnecessary re-renders
  if (prevProps.shouldUpdate !== nextProps.shouldUpdate && nextProps.shouldUpdate) {
    return false; // Re-render if shouldUpdate changed to true
  }
  
  if (prevProps.items.length !== nextProps.items.length) {
    return false; // Re-render if item count changed
  }
  
  // Check if any items actually changed
  for (let i = 0; i < prevProps.items.length; i++) {
    if (prevProps.items[i].id !== nextProps.items[i].id) {
      return false; // Re-render if item IDs changed
    }
  }
  
  return true; // Skip re-render if nothing changed
});

OptimizedStatic.displayName = 'OptimizedStatic';

export default OptimizedStatic;