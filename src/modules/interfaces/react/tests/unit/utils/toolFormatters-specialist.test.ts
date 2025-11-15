/**
 * Tool formatter tests for specialist tools
 *
 * Tests the formatting of validation_specialist and mem0_memory tool inputs
 * for display in the UI.
 */
import { describe, it, expect } from '@jest/globals';

describe('Specialist tool formatters', () => {
  describe('validation_specialist formatter', () => {
    it('formats validation specialist with finding and artifacts', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        finding_description: 'SQL injection in /api/users?id=1 allows data extraction',
        artifact_paths: ['baseline.html', 'exploit.html'],
        claimed_severity: 'HIGH'
      };

      const formatted = toolFormatters.validation_specialist(input);

      expect(formatted).toContain('validating finding');
      expect(formatted).toContain('2 artifacts');
      expect(formatted).toContain('SQL injection');
    });

    it('truncates long finding descriptions', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const longFinding = 'A'.repeat(100);
      const input = {
        finding_description: longFinding,
        artifact_paths: ['test.html']
      };

      const formatted = toolFormatters.validation_specialist(input);

      // Should be truncated to ~60 chars + "..."
      expect(formatted.length).toBeLessThan(100);
      expect(formatted).toContain('...');
    });

    it('handles empty artifact_paths array', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        finding_description: 'Test finding',
        artifact_paths: []
      };

      const formatted = toolFormatters.validation_specialist(input);

      expect(formatted).toContain('0 artifacts');
      expect(formatted).toContain('Test finding');
    });

    it('handles camelCase field names (artifactPaths)', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        finding: 'XSS vulnerability',
        artifactPaths: ['poc1.html', 'poc2.html', 'poc3.html']
      };

      const formatted = toolFormatters.validation_specialist(input);

      expect(formatted).toContain('3 artifacts');
      expect(formatted).toContain('XSS');
    });

    it('handles missing fields gracefully', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {};

      const formatted = toolFormatters.validation_specialist(input);

      expect(formatted).toContain('0 artifacts');
      // Should not crash
      expect(typeof formatted).toBe('string');
    });
  });

  describe('mem0_memory formatter enhancements', () => {
    it('formats list action without truncating JSON', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        action: 'list',
        query: 'vulnerabilities'
      };

      const formatted = toolFormatters.mem0_memory(input);

      expect(formatted).toContain('list memories');
      // Should NOT show truncated JSON
      expect(formatted).not.toContain('[{');
    });

    it('formats retrieve action without truncating JSON', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        action: 'retrieve',
        query: 'findings'
      };

      const formatted = toolFormatters.mem0_memory(input);

      expect(formatted).toContain('retrieve memories');
      expect(formatted).not.toContain('[{');
    });

    it('still shows preview for store action', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        action: 'store',
        content: 'Important finding about SQLi'
      };

      const formatted = toolFormatters.mem0_memory(input);

      expect(formatted).toContain('storing memory');
      expect(formatted).toContain('SQLi');
    });

    it('shows TOON plan preview for store_plan', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const plan = `plan_overview[1]{objective,current_phase,total_phases}:
  Complete security assessment,1,3
plan_phases[3]{id,title,status,criteria}:
  1,Recon,active,map attack surface
  2,Testing,pending,validate findings
  3,Report,pending,document results`;

      const input = {
        action: 'store_plan',
        content: plan
      };

      const formatted = toolFormatters.mem0_memory(input);

      expect(formatted).toContain('plan:');
      expect(formatted).toContain('Complete security assessment');
      expect(formatted).toContain('Phase 1/3');
    });

    it('extracts TOON plan from nested JSON response', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      // Simulate the actual response format from logs
      const nestedResponse = JSON.stringify({
        results: [{
          id: '17b1e003-6d04-4209-a1a2-b978a9bbe9f2',
          memory: '[PLAN] plan_overview[1]{objective,current_phase,total_phases}:\n  Assess ripio.com for bug bounty,1,4\nplan_phases[4]{id,title,status,criteria}:\n  1,Discovery,active,Map attack surface\n  2,Testing,pending,Validate findings\n  3,Exploit,pending,Confirm vulnerabilities\n  4,Report,pending,Document results',
          event: 'ADD',
          hash: '9275c1029ef5869b64f5a80e42c7193a'
        }]
      });

      const input = {
        action: 'store_plan',
        content: nestedResponse
      };

      const formatted = toolFormatters.mem0_memory(input);

      // Should successfully extract nested JSON and parse TOON format
      expect(formatted).toContain('store_plan');
      expect(formatted).toContain('plan:');
      // The TOON parser extracts the structured plan, should see PLAN marker
      expect(formatted).toContain('[PLAN]');
    });

    it('handles nested JSON with memory field', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const nestedResponse = JSON.stringify({
        results: [{
          memory: '[OBSERVATION] Direct curl requests to ripio.com return 403',
          event: 'ADD'
        }]
      });

      const input = {
        action: 'store',
        content: nestedResponse
      };

      const formatted = toolFormatters.mem0_memory(input);

      expect(formatted).toContain('storing memory');
      expect(formatted).toContain('content:');
      expect(formatted).toContain('OBSERVATION');
      expect(formatted).toContain('403');
    });

    it('handles malformed JSON gracefully', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        action: 'store',
        content: '{invalid json content...'
      };

      const formatted = toolFormatters.mem0_memory(input);

      // Should not crash, should show truncated original content
      expect(formatted).toContain('storing memory');
      expect(typeof formatted).toBe('string');
    });

    it('handles unknown action gracefully', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const input = {
        action: 'unknown'
      };

      const formatted = toolFormatters.mem0_memory(input);

      // Should return empty string for unknown action
      expect(formatted).toBe('');
    });
  });

  describe('formatter error handling', () => {
    it('handles null input', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const formatted = toolFormatters.validation_specialist(null as any);

      // Should not crash
      expect(typeof formatted).toBe('string');
    });

    it('handles undefined input', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const formatted = toolFormatters.validation_specialist(undefined as any);

      // Should not crash
      expect(typeof formatted).toBe('string');
    });

    it('handles non-object input', async () => {
      const mod: any = await import('../../../src/utils/toolFormatters.js');
      const { toolFormatters } = mod;

      const formatted = toolFormatters.validation_specialist('string input' as any);

      // Should not crash
      expect(typeof formatted).toBe('string');
    });
  });
});
