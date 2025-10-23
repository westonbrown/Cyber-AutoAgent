/**
 * Renderer Snapshot Tests
 *
 * Ensures consistent rendering across all specialized renderers
 */

import React from 'react';
import { render } from 'ink-testing-library';
import { describe, it, expect } from '@jest/globals';
import {
  CoreToolRenderer,
  ShellHttpRenderer,
  MemoryRenderer,
  GenericRenderer,
  MetricsRenderer
} from '../../../src/components/renderers/index.js';
import { EventType } from '../../../src/types/events.js';

describe('Renderer Snapshots', () => {
  describe('CoreToolRenderer', () => {
    it('renders tool_start event correctly', () => {
      const event = {
        type: 'tool_start',
        tool_name: 'nmap',
        tool_input: { target: '192.168.1.1', ports: '1-1000' },
        id: 'tool-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<CoreToolRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders tool_output event correctly', () => {
      const event = {
        type: 'tool_output',
        tool: 'nmap',
        output: 'Starting Nmap scan on 192.168.1.1...\nPort 80 is open',
        id: 'tool-2',
        timestamp: '2025-01-01T00:00:01Z'
      };

      const { lastFrame } = render(<CoreToolRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders tool_end event correctly', () => {
      const event = {
        type: 'tool_end',
        tool: 'nmap',
        duration: 1500,
        id: 'tool-3',
        timestamp: '2025-01-01T00:00:02Z'
      };

      const { lastFrame } = render(<CoreToolRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders tool_error event correctly', () => {
      const event = {
        type: 'tool_error',
        tool: 'nmap',
        error: 'Connection timeout',
        id: 'tool-4',
        timestamp: '2025-01-01T00:00:03Z'
      };

      const { lastFrame } = render(<CoreToolRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });
  });

  describe('ShellHttpRenderer', () => {
    it('renders shell command correctly', () => {
      const event = {
        type: 'shell_command',
        command: 'ls -la /var/www',
        id: 'cmd-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<ShellHttpRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders HTTP request correctly', () => {
      const event = {
        type: 'http_request',
        method: 'GET',
        url: 'https://api.example.com/v1/users',
        headers: { 'Content-Type': 'application/json' },
        id: 'http-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<ShellHttpRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders HTTP response correctly', () => {
      const event = {
        type: 'http_response',
        statusCode: 200,
        responseTime: 250,
        body: { status: 'success' },
        id: 'http-2',
        timestamp: '2025-01-01T00:00:01Z'
      };

      const { lastFrame } = render(<ShellHttpRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });
  });

  describe('MemoryRenderer', () => {
    it('renders memory_store event correctly', () => {
      const event = {
        type: 'memory_store',
        key: 'scan-results-001',
        value: { ports: [80, 443], vulnerabilities: 2 },
        id: 'mem-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<MemoryRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders reasoning event correctly', () => {
      const event = {
        type: 'reasoning',
        content: 'Analyzing the scan results to identify critical vulnerabilities...',
        isReasoning: true,
        id: 'reason-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<MemoryRenderer event={event} terminalWidth={80} />);
      expect(lastFrame()).toMatchSnapshot();
    });
  });

  describe('MetricsRenderer', () => {
    it('renders metrics in collapsed mode', () => {
      const event = {
        type: 'metrics_update',
        usage: { inputTokens: 1000, outputTokens: 500, totalTokens: 1500 },
        cost: { totalCost: 0.045 },
        metrics: { latencyMs: 2500 },
        id: 'metrics-1',
        sessionId: 'session-123',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<MetricsRenderer event={event} collapsed={true} />);
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders metrics in expanded mode', () => {
      const event = {
        type: 'metrics_update',
        usage: { inputTokens: 1000, outputTokens: 500, totalTokens: 1500 },
        cost: { totalCost: 0.045, modelCost: 0.04 },
        metrics: { latencyMs: 2500, toolCallCount: 5 },
        id: 'metrics-2',
        sessionId: 'session-123',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(<MetricsRenderer event={event} collapsed={false} />);
      expect(lastFrame()).toMatchSnapshot();
    });
  });

  describe('GenericRenderer', () => {
    it('renders unknown event type with metadata', () => {
      const event = {
        type: 'custom_event',
        content: 'This is a custom event',
        customField: 'value123',
        id: 'custom-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(
        <GenericRenderer event={event} terminalWidth={80} showMetadata={true} />
      );
      expect(lastFrame()).toMatchSnapshot();
    });

    it('renders unknown event without metadata', () => {
      const event = {
        type: 'simple_event',
        content: 'Simple content',
        id: 'simple-1',
        timestamp: '2025-01-01T00:00:00Z'
      };

      const { lastFrame } = render(
        <GenericRenderer event={event} terminalWidth={80} showMetadata={false} />
      );
      expect(lastFrame()).toMatchSnapshot();
    });
  });
});
