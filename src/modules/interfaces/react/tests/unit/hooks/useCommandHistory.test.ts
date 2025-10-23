/**
 * useCommandHistory Tests
 *
 * Tests for command history navigation hook
 */

import { describe, it, expect } from '@jest/globals';
import { useCommandHistory } from '../../../src/hooks/useCommandHistory.js';
import { renderHook, act } from '@testing-library/react-hooks';

describe('useCommandHistory', () => {
  it('initializes with empty history', () => {
    const { result } = renderHook(() => useCommandHistory());
    expect(result.current.getHistory()).toEqual([]);
    expect(result.current.historyPosition).toBe(-1);
  });

  it('adds commands to history', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('command1');
      result.current.addCommand('command2');
    });

    expect(result.current.getHistory()).toEqual(['command1', 'command2']);
  });

  it('does not add empty commands', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('');
      result.current.addCommand('  ');
    });

    expect(result.current.getHistory()).toEqual([]);
  });

  it('does not add duplicate consecutive commands', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('command1');
      result.current.addCommand('command1');
      result.current.addCommand('command2');
    });

    expect(result.current.getHistory()).toEqual(['command1', 'command2']);
  });

  it('navigates through history with previous', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
      result.current.addCommand('cmd3');
    });

    let item: string | null;

    act(() => {
      item = result.current.navigatePrevious();
    });
    expect(item).toBe('cmd3');

    act(() => {
      item = result.current.navigatePrevious();
    });
    expect(item).toBe('cmd2');

    act(() => {
      item = result.current.navigatePrevious();
    });
    expect(item).toBe('cmd1');
  });

  it('navigates through history with next', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
      result.current.addCommand('cmd3');
    });

    // Go back
    act(() => {
      result.current.navigatePrevious();
      result.current.navigatePrevious();
    });

    let item: string | null;

    // Go forward
    act(() => {
      item = result.current.navigateNext();
    });
    expect(item).toBe('cmd3');
  });

  it('returns null when navigating past bounds', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
    });

    let item: string | null;

    // Navigate back
    act(() => {
      result.current.navigatePrevious();
    });

    // Try to go back further
    act(() => {
      item = result.current.navigatePrevious();
    });
    expect(item).toBe('cmd1'); // Should stay at first item

    // Navigate forward past end
    act(() => {
      result.current.navigateNext();
      item = result.current.navigateNext();
    });
    expect(item).toBeNull();
  });

  it('clears history', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
    });

    expect(result.current.getHistory().length).toBe(2);

    act(() => {
      result.current.clearHistory();
    });

    expect(result.current.getHistory()).toEqual([]);
    expect(result.current.historyPosition).toBe(-1);
  });

  it('respects maxItems limit', () => {
    const { result } = renderHook(() => useCommandHistory({ maxItems: 3 }));

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
      result.current.addCommand('cmd3');
      result.current.addCommand('cmd4');
      result.current.addCommand('cmd5');
    });

    const history = result.current.getHistory();
    expect(history.length).toBe(3);
    expect(history).toEqual(['cmd3', 'cmd4', 'cmd5']);
  });

  it('respects enabled flag', () => {
    const { result } = renderHook(() => useCommandHistory({ enabled: false }));

    act(() => {
      result.current.addCommand('cmd1');
    });

    expect(result.current.getHistory()).toEqual([]);
    expect(result.current.enabled).toBe(false);
  });

  it('initializes with provided history', () => {
    const { result } = renderHook(() =>
      useCommandHistory({ initialHistory: ['existing1', 'existing2'] })
    );

    expect(result.current.getHistory()).toEqual(['existing1', 'existing2']);
  });

  it('gets current item correctly', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
    });

    expect(result.current.getCurrentItem()).toBeNull();

    act(() => {
      result.current.navigatePrevious();
    });

    expect(result.current.getCurrentItem()).toBe('cmd2');
  });

  it('resets position after adding command', () => {
    const { result } = renderHook(() => useCommandHistory());

    act(() => {
      result.current.addCommand('cmd1');
      result.current.addCommand('cmd2');
    });

    act(() => {
      result.current.navigatePrevious();
    });

    expect(result.current.historyPosition).toBeGreaterThan(-1);

    act(() => {
      result.current.addCommand('cmd3');
    });

    expect(result.current.historyPosition).toBe(-1);
  });
});
