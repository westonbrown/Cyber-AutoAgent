/**
 * Lazy-loaded Components
 * 
 * Heavy components that are loaded on-demand to improve initial load performance
 */

import React, { Suspense } from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';

// Loading fallback component
const LoadingFallback: React.FC<{ componentName: string }> = ({ componentName }) => {
  const theme = themeManager.getCurrentTheme();
  return (
    <Box padding={1}>
      <Text color={theme.muted}>Loading {componentName}...</Text>
    </Box>
  );
};

// Lazy load heavy components
export const LazyConfigEditor = React.lazy(() => 
  import('./ConfigEditor.js').then(module => ({ default: module.ConfigEditor }))
);

export const LazyDocumentationViewer = React.lazy(() => 
  import('./DocumentationViewer.js').then(module => ({ default: module.DocumentationViewer }))
);

export const LazyModuleSelector = React.lazy(() => 
  import('./ModuleSelector.js').then(module => ({ default: module.ModuleSelector }))
);

export const LazySwarmDisplay = React.lazy(() => 
  import('./SwarmDisplay.js').then(module => ({ default: module.SwarmDisplay }))
);

export const LazyUnconstrainedTerminal = React.lazy(() => 
  import('./UnconstrainedTerminal.js').then(module => ({ default: module.UnconstrainedTerminal }))
);

// Wrapper components with Suspense boundaries
export const ConfigEditorLazy: React.FC<any> = (props) => (
  <Suspense fallback={<LoadingFallback componentName="Configuration Editor" />}>
    <LazyConfigEditor {...props} />
  </Suspense>
);

export const DocumentationViewerLazy: React.FC<any> = (props) => (
  <Suspense fallback={<LoadingFallback componentName="Documentation" />}>
    <LazyDocumentationViewer {...props} />
  </Suspense>
);

export const ModuleSelectorLazy: React.FC<any> = (props) => (
  <Suspense fallback={<LoadingFallback componentName="Module Selector" />}>
    <LazyModuleSelector {...props} />
  </Suspense>
);

export const SwarmDisplayLazy: React.FC<any> = (props) => (
  <Suspense fallback={<LoadingFallback componentName="Swarm Display" />}>
    <LazySwarmDisplay {...props} />
  </Suspense>
);

export const UnconstrainedTerminalLazy: React.FC<any> = (props) => (
  <Suspense fallback={<LoadingFallback componentName="Terminal" />}>
    <LazyUnconstrainedTerminal {...props} />
  </Suspense>
);