/**
 * Unified Static Content Component
 *
 * @deprecated This component is not used by the current UI flow and renders a Header internally,
 * which could reintroduce duplicate banner rendering if adopted unintentionally.
 * Banner rendering is centralized in `components/MainAppView.tsx`. Prefer extending
 * `MainAppView` instead of using this component.
 */

import React, { useMemo, useEffect } from 'react';
import { Box, Text, Static } from 'ink';
import { Header } from './Header.js';
import { OperationStatusDisplay } from './OperationStatusDisplay.js';
import { VirtualizedOutput, useVirtualizedHistory } from './VirtualizedOutput.js';
import { LoadingIndicator } from './LoadingIndicator.js';

interface StaticContentItem {
  id: string;
  type: 'header' | 'status' | 'history' | 'spacer' | 'virtualized-history' | 'loading';
  content?: string;
  timestamp?: Date;
  level?: 'info' | 'error' | 'warning' | 'success';
  data?: any;
}

interface UnifiedStaticContentProps {
  // Header props
  version: string;
  terminalWidth: number;
  nightly: boolean;
  
  // Status props
  activeOperation?: any;
  flowState?: any;
  
  // History props
  operationHistory: Array<{
    id: string;
    content: string;
    type: string;
    timestamp: Date;
  }>;
  
  // Theme
  currentTheme: any;
  
  // Key for forcing updates
  staticKey?: number;
  
  // Performance settings
  useVirtualization?: boolean;
  maxHistoryItems?: number;
  
  // Loading state
  isLoading?: boolean;
  loadingText?: string;
}

export const UnifiedStaticContent: React.FC<UnifiedStaticContentProps> = React.memo(({
  version,
  terminalWidth,
  nightly,
  activeOperation,
  flowState,
  operationHistory,
  currentTheme,
  staticKey = 0,
  useVirtualization = true,
  maxHistoryItems = 50,
  isLoading = false,
  loadingText = 'Processing'
}) => {
  // Dev-time safeguard to prevent accidental usage
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn('[Deprecated] UnifiedStaticContent is deprecated. Use MainAppView for centralized banner rendering.');
    }
  }, []);
  
  // Convert history for virtualized output
  const virtualizedHistory = useVirtualizedHistory(operationHistory);
  
  // Determine if we should use virtualization
  const shouldUseVirtualization = useVirtualization && operationHistory.length > maxHistoryItems;
  
  // Create stable static items with consistent keys
  const staticItems = useMemo(() => {
    const items: StaticContentItem[] = [];
    
    // Always include header as first item (stable key)
    items.push({
      id: 'app-header',
      type: 'header',
      data: { version, terminalWidth, nightly }
    });
    
    // Add operation status if active (stable key)
    if (activeOperation) {
      items.push({
        id: 'operation-status',
        type: 'status',
        data: { activeOperation, flowState }
      });
    }
    
    // Add loading indicator if loading (stable key)
    if (isLoading) {
      items.push({
        id: 'loading-indicator',
        type: 'loading',
        data: { text: loadingText, showPhases: true }
      });
    }
    
    // Add spacer after header/status/loading
    items.push({
      id: 'header-spacer',
      type: 'spacer'
    });
    
    // Use either virtualized or regular history display
    if (shouldUseVirtualization) {
      // Single virtualized history item
      items.push({
        id: 'virtualized-history',
        type: 'virtualized-history',
        data: { virtualizedHistory, currentTheme }
      });
    } else {
      // Individual history items for small lists
      const filteredHistory = operationHistory.filter(entry => 
        entry.type !== 'command' || !entry.content.startsWith('/')
      );
      
      filteredHistory.forEach((entry) => {
        items.push({
          id: `history-${entry.id}`, // Use entry.id for stability
          type: 'history',
          content: entry.content,
          timestamp: entry.timestamp,
          level: entry.type as any
        });
      });
    }
    
    return items;
  }, [version, terminalWidth, nightly, activeOperation, flowState, operationHistory, virtualizedHistory, shouldUseVirtualization, currentTheme, staticKey, isLoading, loadingText]);
  
  // Create stable item keys for Static component
  const itemKeys = useMemo(() => 
    staticItems.map(item => item.id), 
    [staticItems]
  );
  
  // Render function for Static items
  const renderItem = React.useCallback((itemId: string) => {
    const item = staticItems.find(i => i.id === itemId);
    if (!item) return <Box key={itemId} />;
    
    switch (item.type) {
      case 'header':
        return (
          <Box key={itemId} flexDirection="column">
            <Header 
              version={item.data.version}
              terminalWidth={item.data.terminalWidth}
              nightly={item.data.nightly}
            />
          </Box>
        );
        
      case 'status':
        if (!item.data.activeOperation) return <Box key={itemId} />;
        return (
          <Box key={itemId} flexDirection="column">
            <OperationStatusDisplay 
              flowState={item.data.flowState}
              currentOperation={{
                id: item.data.activeOperation.id,
                currentStep: 1,
                totalSteps: 1,
                description: item.data.activeOperation.description || 'Running assessment',
                startTime: new Date(),
                status: item.data.activeOperation.status || 'running'
              }}
              showFlowProgress={false}
            />
          </Box>
        );
        
      case 'loading':
        return (
          <Box key={itemId} flexDirection="column" marginY={1}>
            <LoadingIndicator
              text={item.data.text}
              showPhases={item.data.showPhases}
              spinnerType="dots"
              color="cyan"
            />
          </Box>
        );
        
      case 'spacer':
        return <Box key={itemId} marginBottom={1} />;
        
      case 'virtualized-history':
        return (
          <Box key={itemId} flexDirection="column">
            <VirtualizedOutput 
              items={item.data.virtualizedHistory}
              height={20}
              showTimestamps={true}
            />
          </Box>
        );
        
      case 'history':
        if (!item.content || !item.timestamp) return <Box key={itemId} />;
        
        const color = item.level === 'error' ? currentTheme.error : 
                     item.level === 'warning' ? currentTheme.warning :
                     item.level === 'success' ? currentTheme.success :
                     currentTheme.foreground;
                     
        return (
          <Box key={itemId} flexDirection="column">
            <Box>
              <Text color={currentTheme.muted}>
                [{item.timestamp.toLocaleTimeString()}]{' '}
              </Text>
              <Text color={color}>
                {item.content}
              </Text>
            </Box>
          </Box>
        );
        
      default:
        return <Box key={itemId} />;
    }
  }, [staticItems, currentTheme]);
  
  // Don't render anything if no items, but this should never happen since header is always included
  // Fallback: render at least a header if something goes wrong with static items generation
  if (itemKeys.length === 0) {
    return (
      <Box flexDirection="column">
        <Header 
          version={version}
          terminalWidth={terminalWidth}
          nightly={nightly}
        />
      </Box>
    );
  }
  
  // Use a stable key to prevent flickering during setup/progress updates
  // Only change when items fundamentally change (not just content updates)
  const stableKey = useMemo(() => {
    // Create a stable key based on item types, not content or staticKey changes
    const keyComponents = [
      staticItems.some(item => item.type === 'header') ? 'header' : '',
      staticItems.some(item => item.type === 'status') ? 'status' : '',
      staticItems.some(item => item.type === 'loading') ? 'loading' : '',
      staticItems.length > 0 ? 'content' : 'empty'
    ].filter(Boolean).join('-');
    
    return `unified-${keyComponents}`;
  }, [staticItems]);

  return (
    <Static key={stableKey} items={itemKeys}>
      {renderItem}
    </Static>
  );
});

UnifiedStaticContent.displayName = 'UnifiedStaticContent';

export default UnifiedStaticContent;