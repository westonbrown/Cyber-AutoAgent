/**
 * ErrorBoundary Component
 * 
 * React error boundary to catch and handle JavaScript errors anywhere in the component tree.
 * Provides graceful error handling with recovery options for the Cyber-AutoAgent interface.
 */

import React, { Component, ReactNode } from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';
import { Header } from './Header.js';
import { loggingService } from '../services/LoggingService.js';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // Log error for debugging
    loggingService.error('ErrorBoundary caught an error:', error, errorInfo);
    
    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleRestart = () => {
    // Force application restart in CLI environment
    process.exit(1);
  };

  render() {
    const theme = themeManager.getCurrentTheme();

    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box flexDirection="column" width="100%">
          {/* Always show header for visual continuity */}
          <Header 
            version="0.1.3" 
            terminalWidth={80} 
            nightly={false} 
          />
          
          <Box flexDirection="column" padding={2}>
            <Box borderStyle="double" borderColor="red" padding={1} marginBottom={1}>
              <Box flexDirection="column">
                <Text color="red" bold>
                  ⚠️ Application Error
                </Text>
                <Text color={theme.muted}>
                  Cyber-AutoAgent encountered an unexpected error
                </Text>
              </Box>
            </Box>

          <Box flexDirection="column" marginBottom={2}>
            <Text color={theme.foreground} bold>
              Error Details:
            </Text>
            <Text color={theme.danger}>
              {this.state.error?.message || 'Unknown error occurred'}
            </Text>
            
            {process.env.NODE_ENV === 'development' && this.state.error?.stack && (
              <Box marginTop={1}>
                <Text color={theme.muted}>
                  Stack trace:
                </Text>
                <Text color={theme.muted}>
                  {this.state.error.stack}
                </Text>
              </Box>
            )}
          </Box>

          <Box flexDirection="column">
            <Text color={theme.info}>
              Recovery Options:
            </Text>
            <Text color={theme.success}>
              • Press R to retry the operation
            </Text>
            <Text color={theme.success}>
              • Press Ctrl+R to restart the application
            </Text>
            <Text color={theme.success}>
              • Press Ctrl+C to exit
            </Text>
          </Box>

          <Box marginTop={2}>
            <Text color={theme.muted}>
              If this error persists, please report it at:
            </Text>
            <Text color={theme.primary}>
              https://github.com/westonbrown/Cyber-AutoAgent/issues
            </Text>
          </Box>
          </Box>
        </Box>
      );
    }

    return this.props.children;
  }
}