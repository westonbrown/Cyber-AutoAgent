/**
 * Documentation Viewer Component
 * Interactive documentation browser for Cyber-AutoAgent
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../themes/theme-manager.js';
import * as fs from 'fs/promises';
import * as path from 'path';

interface DocumentInfo {
  name: string;
  file: string;
  description: string;
}

interface DocumentationViewerProps {
  onClose: () => void;
  selectedDoc?: number;
}

export const DocumentationViewer: React.FC<DocumentationViewerProps> = React.memo(({ onClose, selectedDoc }) => {
  const theme = themeManager.getCurrentTheme();
  const [selectedIndex, setSelectedIndex] = useState(selectedDoc ? selectedDoc - 1 : 0);
  const [viewMode, setViewMode] = useState<'list' | 'view'>(selectedDoc ? 'view' : 'list');
  const [documentContent, setDocumentContent] = useState<string>('');
  const [scrollOffset, setScrollOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const documents: DocumentInfo[] = [
    { 
      name: 'User Instructions', 
      file: 'user-instructions.md', 
      description: 'Complete guide for using Cyber-AutoAgent effectively' 
    },
    { 
      name: 'Architecture Overview', 
      file: 'architecture.md', 
      description: 'System design, components, and technical details' 
    },
    { 
      name: 'Deployment Guide', 
      file: 'deployment.md', 
      description: 'Installation options and setup instructions' 
    },
    { 
      name: 'Observability & Evaluation', 
      file: 'observability-evaluation.md', 
      description: 'Monitoring, tracing, and quality metrics' 
    },
    { 
      name: 'Memory System', 
      file: 'memory.md', 
      description: 'Knowledge persistence and retrieval system' 
    },
    { 
      name: 'Terminal Interface', 
      file: 'terminal-frontend.md', 
      description: 'React CLI components and user interface' 
    },
    { 
      name: 'Prompt Management', 
      file: 'prompt_management.md', 
      description: 'Dynamic prompt configuration with Langfuse' 
    }
  ];

  // Load document content
  useEffect(() => {
    if (viewMode === 'view') {
      loadDocument(documents[selectedIndex].file);
    }
  }, [viewMode, selectedIndex]);

  // Fallback documentation content in case file loading fails
  const getFallbackContent = (filename: string): string => {
    switch (filename) {
      case 'user-instructions.md':
        return `# Cyber-AutoAgent User Instructions

## ▶ Getting Started

Welcome to Cyber-AutoAgent, an autonomous cybersecurity assessment tool.

### First Time Setup

When you first launch Cyber-AutoAgent, you'll be presented with a deployment mode selection:

1. **Local CLI** - Minimal setup, runs directly in Python
2. **Single Container** - Docker isolation without observability  
3. **Enterprise** (Recommended) - Full stack with monitoring and evaluation

### Basic Usage Patterns

#### Guided Flow (Step-by-Step)
\`\`\`bash
◆ general > target https://testphp.vulnweb.com
✓ Target set
◆ general > execute focus on SQL injection
\`\`\`

## ■ Safety & Authorization

**CRITICAL**: Only use Cyber-AutoAgent on systems you have explicit authorization to test.

### Authorization Flow
1. **Target Confirmation**: Shows exact target and module
2. **Legal Acknowledgment**: Type 'y' to confirm authorization
3. **Final Confirmation**: Type 'y' again to proceed

### Authorized Test Targets
- https://testphp.vulnweb.com (Public test site)
- Your own applications and infrastructure
- Systems with written penetration testing agreements

## ▣ Commands Reference

### Assessment Commands
- \`target <url>\` - Set assessment target
- \`execute [objective]\` - Start assessment with optional focus
- \`reset\` - Clear current configuration

### Configuration Commands
- \`/config\` - View configuration
- \`/help\` - Show all commands
- \`/docs\` - Browse documentation
- \`/memory list\` - View previous findings

For complete documentation, see the /docs folder in your installation.`;

      case 'architecture.md':
        return `# Cyber-AutoAgent Architecture

## System Overview

Cyber-AutoAgent is built on a modern, scalable architecture:

- **Python Backend**: Strands SDK framework
- **React CLI**: Terminal interface with Ink
- **Docker**: Containerized deployment
- **Observability**: Langfuse integration
- **Evaluation**: Ragas metrics system

## Key Components

### Core Agent (src/cyberautoagent.py)
- Main entry point and CLI argument parsing
- Strands SDK agent initialization
- Assessment orchestration

### React Interface (src/modules/interfaces/react/)
- Professional terminal UI
- Real-time event streaming
- Configuration management

### Memory System (src/modules/tools/memory.py)
- Persistent knowledge storage
- FAISS/OpenSearch backends
- Cross-assessment learning

For detailed architecture information, refer to the source code and inline documentation.`;

      default:
        return `# ${filename}

Documentation for this file is not available in fallback mode.

To access the complete documentation:

1. Ensure you're running from the project root directory
2. Check that the /docs folder exists
3. Verify file permissions

Available documentation includes:
- User Instructions
- Architecture Overview  
- Deployment Guide
- Memory System
- Observability & Evaluation

Use /help for available commands or refer to the project repository for complete documentation.`;
    }
  };

  const loadDocument = async (filename: string) => {
    setLoading(true);
    setError(null);
    try {
      // Get current working directory info for debugging
      const cwd = process.cwd();
      // console.log('[DocumentationViewer] Current working directory:', cwd);
      
      // Try to load from file system first
      const possiblePaths = [
        path.join(cwd, 'docs', filename),
        path.join(cwd, '..', 'docs', filename),
        path.join(cwd, '..', '..', 'docs', filename),
        path.join(cwd, '..', '..', '..', 'docs', filename),
        path.join(cwd, '..', '..', '..', '..', 'docs', filename),
        path.join('/app', 'docs', filename)
      ];
      
      let content = '';
      let foundPath = '';
      
      for (const testPath of possiblePaths) {
        try {
          content = await fs.readFile(testPath, 'utf-8');
          foundPath = testPath;
          // console.log('[DocumentationViewer] Successfully loaded from:', testPath);
          break;
        } catch (err) {
          continue;
        }
      }
      
      // If file loading failed, use fallback content
      if (!foundPath) {
        // console.warn('[DocumentationViewer] File loading failed, using fallback content for:', filename);
        content = getFallbackContent(filename);
      }
      
      setDocumentContent(content);
      setScrollOffset(0);
    } catch (err) {
      // If everything fails, use fallback content
      // console.error('[DocumentationViewer] All loading methods failed, using fallback for:', filename);
      setDocumentContent(getFallbackContent(filename));
      setScrollOffset(0);
    } finally {
      setLoading(false);
    }
  };

  // Handle keyboard input with high priority to override other handlers
  useInput((input, key) => {
    if (key.escape || (key.ctrl && input === 'c')) {
      if (viewMode === 'view') {
        setViewMode('list');
        setDocumentContent('');
      } else {
        onClose();
      }
      return;
    }

    if (viewMode === 'list') {
      if (key.upArrow) {
        setSelectedIndex(prev => prev > 0 ? prev - 1 : documents.length - 1);
      } else if (key.downArrow) {
        setSelectedIndex(prev => prev < documents.length - 1 ? prev + 1 : 0);
      } else if (key.return) {
        setViewMode('view');
      }
    } else {
      // Document view mode
      const linesPerPage = 20;
      const totalLines = documentContent.split('\n').length;
      
      if (key.upArrow || input === 'k') {
        setScrollOffset(prev => Math.max(0, prev - 1));
      } else if (key.downArrow || input === 'j') {
        setScrollOffset(prev => Math.min(totalLines - linesPerPage, prev + 1));
      } else if (key.pageDown) {
        setScrollOffset(prev => Math.min(totalLines - linesPerPage, prev + linesPerPage));
      } else if (key.pageUp) {
        setScrollOffset(prev => Math.max(0, prev - linesPerPage));
      } else if (input === 'g') {
        setScrollOffset(0); // Go to top
      } else if (input === 'G') {
        setScrollOffset(Math.max(0, totalLines - linesPerPage)); // Go to bottom
      }
    }
  }, { isActive: true });

  const renderDocumentList = () => (
    <Box flexDirection="column">
      <Box marginBottom={1}>
        <Text color={theme.primary} bold>■ Cyber-AutoAgent Documentation</Text>
      </Box>
      
      <Box borderStyle="single" borderColor={theme.accent} paddingX={1} flexDirection="column">
        <Text color={theme.muted}>Select a document to read:</Text>
        <Box marginTop={1} />
        
        {documents.map((doc, index) => (
          <Box key={index} marginBottom={1}>
            <Text color={index === selectedIndex ? theme.primary : theme.foreground}>
              {index === selectedIndex ? '▶ ' : '  '}
              {index + 1}. {doc.name}
            </Text>
            <Text color={theme.muted}>
              {'     '}{doc.description}
            </Text>
          </Box>
        ))}
      </Box>
      
      <Box marginTop={1}>
        <Text color={theme.muted}>
          Use ↑↓ to navigate, Enter to read, Esc to exit
        </Text>
      </Box>
    </Box>
  );

  const renderDocumentView = () => {
    if (loading) {
      return (
        <Box>
          <Text color={theme.info}>Loading document...</Text>
        </Box>
      );
    }

    if (error) {
      return (
        <Box flexDirection="column">
          <Text color="red">Error: {error}</Text>
          <Text color={theme.muted}>Press Esc to go back</Text>
        </Box>
      );
    }

    const lines = documentContent.split('\n');
    const visibleLines = lines.slice(scrollOffset, scrollOffset + 20);
    const currentLine = scrollOffset + 1;
    const totalLines = lines.length;
    const scrollPercentage = Math.round((currentLine / totalLines) * 100);

    return (
      <Box flexDirection="column" height="100%">
        {/* Header */}
        <Box 
          borderStyle="single" 
          borderColor={theme.accent} 
          paddingX={1} 
          marginBottom={1}
          justifyContent="space-between"
        >
          <Text color={theme.primary} bold>
            ▎{documents[selectedIndex].name}
          </Text>
          <Text color={theme.muted}>
            Line {currentLine}/{totalLines} ({scrollPercentage}%)
          </Text>
        </Box>

        {/* Content */}
        <Box flexDirection="column" paddingX={1}>
          {visibleLines.map((line, index) => (
            <Text key={index} color={theme.foreground}>
              {formatMarkdownLine(line)}
            </Text>
          ))}
        </Box>

        {/* Footer */}
        <Box marginTop={1} paddingX={1}>
          <Text color={theme.muted}>
            ↑↓/jk: scroll | PgUp/PgDn: page | g/G: top/bottom | Esc: back to list
          </Text>
        </Box>
      </Box>
    );
  };

  // Simple markdown formatting
  const formatMarkdownLine = (line: string): string => {
    // Headers
    if (line.startsWith('# ')) return `\n${line.substring(2).toUpperCase()}\n${'═'.repeat(line.length - 2)}`;
    if (line.startsWith('## ')) return `\n${line.substring(3)}\n${'─'.repeat(line.length - 3)}`;
    if (line.startsWith('### ')) return `• ${line.substring(4)}`;
    
    // Code blocks
    if (line.startsWith('```')) return '─'.repeat(50);
    
    // Lists
    if (line.startsWith('- ')) return `  • ${line.substring(2)}`;
    if (line.match(/^\d+\. /)) return `  ${line}`;
    
    // Bold (simple replacement)
    line = line.replace(/\*\*(.*?)\*\*/g, '$1');
    
    return line;
  };

  return (
    <Box flexDirection="column" width="100%" height="100%">
      <Box 
        flexDirection="column" 
        padding={1}
        borderStyle="round"
        borderColor={theme.accent}
        marginTop={1}
      >
        {viewMode === 'list' ? renderDocumentList() : renderDocumentView()}
      </Box>
    </Box>
  );
});

DocumentationViewer.displayName = 'DocumentationViewer';