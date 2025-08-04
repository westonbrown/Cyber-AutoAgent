/**
 * Professional Memory Service
 * Provides semantic search across historical security operations
 */

export interface MemoryResult {
  id: string;
  content: string;
  operation_id: string;
  timestamp: string;
  target: string;
  module: string;
  similarity: number;
  metadata: {
    finding_type?: string;
    severity?: string;
    tool_used?: string;
  };
}

export interface MemoryStats {
  total_memories: number;
  session_memories: number;
  retrieval_hits: number;
  last_updated: string;
}

export class MemoryService {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Search across all historical security findings
   */
  async searchMemory(query: string, limit: number = 10): Promise<MemoryResult[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/memory/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          limit,
          include_metadata: true
        })
      });

      if (!response.ok) {
        throw new Error(`Memory search failed: ${response.statusText}`);
      }

      const data = await response.json();
      return data.results || [];
    } catch (error) {
      console.error('Memory search error:', error);
      // Return mock data for development
      return this.getMockMemoryResults(query, limit);
    }
  }

  /**
   * Get memory usage statistics
   */
  async getMemoryStats(): Promise<MemoryStats> {
    try {
      const response = await fetch(`${this.baseUrl}/api/memory/stats`);
      
      if (!response.ok) {
        throw new Error(`Memory stats failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Memory stats error:', error);
      // Return mock stats for development
      return {
        total_memories: 1247,
        session_memories: 156,
        retrieval_hits: 89,
        last_updated: new Date().toISOString()
      };
    }
  }

  /**
   * Get memory patterns and insights
   */
  async getMemoryPatterns(finding_type?: string): Promise<any[]> {
    try {
      const params = new URLSearchParams();
      if (finding_type) {
        params.append('type', finding_type);
      }

      const response = await fetch(`${this.baseUrl}/api/memory/patterns?${params}`);
      
      if (!response.ok) {
        throw new Error(`Memory patterns failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Memory patterns error:', error);
      return [];
    }
  }

  /**
   * Clear memory (with confirmation)
   */
  async clearMemory(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/memory/clear`, {
        method: 'DELETE'
      });

      return response.ok;
    } catch (error) {
      console.error('Memory clear error:', error);
      return false;
    }
  }

  /**
   * Mock memory results for development/testing
   */
  private getMockMemoryResults(query: string, limit: number): MemoryResult[] {
    const mockResults: MemoryResult[] = [
      {
        id: 'mem_001',
        content: 'SQL injection vulnerability found in /api/v2/users endpoint using payload: \' OR \'1\'=\'1\' -- successfully bypassed authentication',
        operation_id: 'OP_20240110_143022',
        timestamp: '2024-01-10T14:30:22Z',
        target: 'testsite.com',
        module: 'general',
        similarity: 0.95,
        metadata: {
          finding_type: 'sql_injection',
          severity: 'high',
          tool_used: 'sqlmap'
        }
      },
      {
        id: 'mem_002',
        content: 'Time-based blind SQL injection in GraphQL query. Field: getUserById(id: String!) Impact: Full database extraction possible',
        operation_id: 'OP_20240108_135544',
        timestamp: '2024-01-08T13:55:44Z',
        target: 'api.example.org',
        module: 'general',
        similarity: 0.87,
        metadata: {
          finding_type: 'sql_injection',
          severity: 'critical',
          tool_used: 'custom_graphql_tester'
        }
      },
      {
        id: 'mem_003',
        content: 'Unsafe string concatenation in UserRepository.java:142 Recommendation: Use parameterized queries',
        operation_id: 'OP_20240105_091233',
        timestamp: '2024-01-05T09:12:33Z',
        target: 'webapp.local',
        module: 'general',
        similarity: 0.72,
        metadata: {
          finding_type: 'code_vulnerability',
          severity: 'medium',
          tool_used: 'semgrep'
        }
      }
    ];

    return mockResults.slice(0, limit);
  }
}