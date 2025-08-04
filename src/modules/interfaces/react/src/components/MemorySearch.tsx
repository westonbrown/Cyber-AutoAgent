import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import TextInput from 'ink-text-input';
import Spinner from 'ink-spinner';
import { themeManager } from '../themes/theme-manager.js';
import { MemoryService, MemoryResult, MemoryStats } from '../services/MemoryService.js';

interface MemorySearchProps {
  onClose: () => void;
}

export const MemorySearch: React.FC<MemorySearchProps> = ({ onClose }) => {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<MemoryResult[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const theme = themeManager.getCurrentTheme();
  const memoryService = new MemoryService();

  // Load memory stats on component mount
  useEffect(() => {
    const loadStats = async () => {
      try {
        const memoryStats = await memoryService.getMemoryStats();
        setStats(memoryStats);
      } catch (err) {
        console.error('Failed to load memory stats:', err);
      }
    };
    loadStats();
  }, []);
  
  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    
    setSearching(true);
    setError(null);
    
    try {
      const searchResults = await memoryService.searchMemory(searchQuery, 10);
      setResults(searchResults);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  };
  
  return (
    <Box flexDirection="column" paddingX={1}>
      <Box marginBottom={1}>
        <Text color={theme.info} bold>🧠 Memory Search</Text>
      </Box>
      
      {/* Memory Statistics */}
      {stats && (
        <Box flexDirection="column" borderStyle="single" borderColor={theme.muted} paddingX={1} marginBottom={1}>
          <Text color={theme.secondary} bold>Memory Statistics:</Text>
          <Box flexDirection="row" gap={2}>
            <Text color={theme.muted}>Total: </Text>
            <Text color={theme.foreground}>{stats.total_memories.toLocaleString()}</Text>
            <Text color={theme.muted}>Session: </Text>
            <Text color={theme.foreground}>{stats.session_memories}</Text>
            <Text color={theme.muted}>Hit Rate: </Text>
            <Text color={theme.success}>{stats.retrieval_hits}%</Text>
          </Box>
        </Box>
      )}
      
      <Box marginBottom={1} borderStyle="single" borderColor={theme.primary} paddingX={1}>
        <Text color={theme.muted}>Search: </Text>
        <TextInput
          value={query}
          onChange={setQuery}
          onSubmit={handleSearch}
          placeholder="Enter target, vulnerability type, or keyword..."
        />
      </Box>
      
      {searching && (
        <Box>
          <Spinner type="dots" />
          <Text color={theme.info}> Searching across {stats?.total_memories || 0} memories...</Text>
        </Box>
      )}
      
      {error && (
        <Box marginBottom={1} borderStyle="single" borderColor={theme.danger} paddingX={1}>
          <Text color={theme.danger}>⚠️ Error: {error}</Text>
        </Box>
      )}
      
      {results.length > 0 && (
        <Box flexDirection="column">
          <Text color={theme.warning} bold>📍 Found {results.length} relevant memories:</Text>
          {results.map((memory, index) => (
            <Box key={memory.id} flexDirection="column" marginTop={1} borderStyle="round" borderColor={memory.metadata.severity === 'critical' ? theme.danger : theme.muted} paddingX={1}>
              <Box flexDirection="row" justifyContent="space-between">
                <Text color={theme.success}>{index + 1}. {memory.target}</Text>
                <Text color={theme.secondary}>({(memory.similarity * 100).toFixed(0)}% match)</Text>
              </Box>
              <Text color={theme.foreground}>{memory.content}</Text>
              <Box flexDirection="row" gap={1}>
                <Text color={theme.muted}>[{memory.operation_id}]</Text>
                <Text color={theme.info}>{memory.module}</Text>
                {memory.metadata.severity && (
                  <Text color={memory.metadata.severity === 'critical' ? theme.danger : memory.metadata.severity === 'high' ? theme.warning : theme.success}>
                    {memory.metadata.severity.toUpperCase()}
                  </Text>
                )}
                {memory.metadata.tool_used && (
                  <Text color={theme.comment}>via {memory.metadata.tool_used}</Text>
                )}
              </Box>
              <Text color={theme.comment}>{new Date(memory.timestamp).toLocaleString()}</Text>
            </Box>
          ))}
        </Box>
      )}
      
      <Box marginTop={2}>
        <Text color={theme.comment}>Press Escape to close • Ctrl+R to refresh stats</Text>
      </Box>
    </Box>
  );
};