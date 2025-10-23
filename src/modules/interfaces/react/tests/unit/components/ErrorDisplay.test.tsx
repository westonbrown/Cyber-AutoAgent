/**
 * ErrorDisplay Tests
 *
 * Tests for consistent error rendering component
 */

import React from 'react';
import { render } from 'ink-testing-library';
import { describe, it, expect } from '@jest/globals';
import { ErrorDisplay, ErrorList } from '../../../src/components/ErrorDisplay.js';

describe('ErrorDisplay', () => {
  it('renders basic error correctly', () => {
    const { lastFrame } = render(<ErrorDisplay message="Something went wrong" />);
    expect(lastFrame()).toContain('ERROR');
    expect(lastFrame()).toContain('Something went wrong');
  });

  it('renders warning type correctly', () => {
    const { lastFrame } = render(<ErrorDisplay message="Warning message" type="warning" />);
    expect(lastFrame()).toContain('WARNING');
    expect(lastFrame()).toContain('Warning message');
  });

  it('renders auth error correctly', () => {
    const { lastFrame } = render(<ErrorDisplay message="Authentication failed" type="auth" />);
    expect(lastFrame()).toContain('AUTH');
    expect(lastFrame()).toContain('Authentication failed');
  });

  it('renders error with details when expanded', () => {
    const { lastFrame } = render(
      <ErrorDisplay
        message="Connection failed"
        details="ECONNREFUSED 127.0.0.1:3000"
        type="network"
        expanded={true}
      />
    );
    expect(lastFrame()).toContain('NETWORK');
    expect(lastFrame()).toContain('Connection failed');
    expect(lastFrame()).toContain('ECONNREFUSED');
  });

  it('renders error with action hint', () => {
    const { lastFrame } = render(
      <ErrorDisplay
        message="Config file missing"
        type="config"
        actionHint="Run setup wizard to create configuration"
      />
    );
    expect(lastFrame()).toContain('CONFIG');
    expect(lastFrame()).toContain('Config file missing');
    expect(lastFrame()).toContain('Run setup wizard');
  });

  it('does not render details when not expanded', () => {
    const { lastFrame } = render(
      <ErrorDisplay
        message="Error"
        details="Hidden details"
        type="error"
        expanded={false}
      />
    );
    expect(lastFrame()).not.toContain('Hidden details');
  });
});

describe('ErrorList', () => {
  it('renders multiple errors', () => {
    const errors = [
      { id: '1', message: 'Error 1', type: 'error' as const },
      { id: '2', message: 'Error 2', type: 'warning' as const },
      { id: '3', message: 'Error 3', type: 'network' as const }
    ];

    const { lastFrame } = render(<ErrorList errors={errors} />);
    expect(lastFrame()).toContain('Error 1');
    expect(lastFrame()).toContain('Error 2');
    expect(lastFrame()).toContain('Error 3');
  });

  it('limits display to maxDisplay count', () => {
    const errors = Array.from({ length: 10 }, (_, i) => ({
      id: String(i),
      message: `Error ${i}`,
      type: 'error' as const
    }));

    const { lastFrame } = render(<ErrorList errors={errors} maxDisplay={3} />);
    expect(lastFrame()).toContain('7 earlier errors hidden');
    expect(lastFrame()).toContain('Error 7');
    expect(lastFrame()).toContain('Error 8');
    expect(lastFrame()).toContain('Error 9');
  });

  it('does not show hidden count when all errors fit', () => {
    const errors = [
      { id: '1', message: 'Error 1', type: 'error' as const },
      { id: '2', message: 'Error 2', type: 'error' as const }
    ];

    const { lastFrame } = render(<ErrorList errors={errors} maxDisplay={5} />);
    expect(lastFrame()).not.toContain('earlier errors hidden');
  });
});
