/**
 * Stream Compression Hook
 * Implements Ctrl+R toggle for agent output streams as per Gemini CLI
 */

import { useState, useCallback } from 'react';
import { useInput } from 'ink';

export interface StreamState {
  isCompressed: boolean;
  showOnlyCurrentStep: boolean;
  showToolExecutions: boolean;
  showThinking: boolean;
}

export const useStreamCompression = () => {
  const [streamState, setStreamState] = useState<StreamState>({
    isCompressed: false,
    showOnlyCurrentStep: false,
    showToolExecutions: true,
    showThinking: true,
  });

  // Handle keyboard shortcuts for stream control
  useInput((input, key) => {
    if (key.ctrl && input === 'r') {
      // Toggle compression mode
      setStreamState(prev => ({
        ...prev,
        isCompressed: !prev.isCompressed,
        showOnlyCurrentStep: !prev.isCompressed,
      }));
    }
    
    if (key.ctrl && input === 't') {
      // Toggle tool execution visibility
      setStreamState(prev => ({
        ...prev,
        showToolExecutions: !prev.showToolExecutions,
      }));
    }
    
    if (key.ctrl && input === 'd') {
      // Toggle debug/thinking information
      setStreamState(prev => ({
        ...prev,
        showThinking: !prev.showThinking,
      }));
    }
  });

  const filterOutput = useCallback((lines: string[]): string[] => {
    if (!streamState.isCompressed) {
      return lines;
    }

    // In compressed mode, show only:
    // - Current step indicators
    // - Major milestone messages
    // - Final results/findings
    // - Error messages
    return lines.filter(line => {
      const lowerLine = line.toLowerCase();
      
      // Always show errors
      if (lowerLine.includes('error') || lowerLine.includes('failed')) {
        return true;
      }
      
      // Show step indicators
      if (lowerLine.includes('step ') && lowerLine.includes('/')) {
        return true;
      }
      
      // Show major milestones
      if (lowerLine.includes('✓') || lowerLine.includes('found') || lowerLine.includes('complete')) {
        return true;
      }
      
      // Show reasoning if enabled
      if (streamState.showThinking && (lowerLine.includes('[thinking]') || lowerLine.includes('reasoning'))) {
        return true;
      }
      
      // Show tool executions if enabled
      if (streamState.showToolExecutions && (lowerLine.includes('[executing]') || lowerLine.includes('running:'))) {
        return true;
      }
      
      return false;
    });
  }, [streamState]);

  const getCompressionStatus = useCallback((): string => {
    if (!streamState.isCompressed) {
      return 'Expanded view • Ctrl+R to compress';
    }
    
    const features = [];
    if (streamState.showToolExecutions) features.push('tools');
    if (streamState.showThinking) features.push('reasoning');
    
    return `Compressed view (${features.join(', ')}) • Ctrl+R to expand`;
  }, [streamState]);

  return {
    streamState,
    filterOutput,
    getCompressionStatus,
  };
};