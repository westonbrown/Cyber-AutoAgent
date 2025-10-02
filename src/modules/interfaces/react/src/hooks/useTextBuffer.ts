/**
 * Text buffer hook with reducer-based state management
 * Inspired by gemini-cli's text-buffer implementation
 * Provides atomic operations for all text changes with proper paste handling
 */

import { useReducer, useCallback } from 'react';

interface TextBufferState {
  text: string;
  cursorPosition: number;
}

type TextBufferAction =
  | { type: 'insert'; payload: string }
  | { type: 'delete_before' }
  | { type: 'delete_after' }
  | { type: 'move_left' }
  | { type: 'move_right' }
  | { type: 'move_start' }
  | { type: 'move_end' }
  | { type: 'set_text'; payload: { text: string; cursorPosition?: number } }
  | { type: 'clear' };

function textBufferReducer(state: TextBufferState, action: TextBufferAction): TextBufferState {
  switch (action.type) {
    case 'insert': {
      const before = state.text.slice(0, state.cursorPosition);
      const after = state.text.slice(state.cursorPosition);
      const newText = before + action.payload + after;

      return {
        text: newText,
        cursorPosition: state.cursorPosition + action.payload.length,
      };
    }

    case 'delete_before': {
      if (state.cursorPosition === 0) return state;

      const before = state.text.slice(0, state.cursorPosition - 1);
      const after = state.text.slice(state.cursorPosition);

      return {
        text: before + after,
        cursorPosition: state.cursorPosition - 1,
      };
    }

    case 'delete_after': {
      if (state.cursorPosition >= state.text.length) return state;

      const before = state.text.slice(0, state.cursorPosition);
      const after = state.text.slice(state.cursorPosition + 1);

      return {
        text: before + after,
        cursorPosition: state.cursorPosition,
      };
    }

    case 'move_left': {
      return {
        ...state,
        cursorPosition: Math.max(0, state.cursorPosition - 1),
      };
    }

    case 'move_right': {
      return {
        ...state,
        cursorPosition: Math.min(state.text.length, state.cursorPosition + 1),
      };
    }

    case 'move_start': {
      return {
        ...state,
        cursorPosition: 0,
      };
    }

    case 'move_end': {
      return {
        ...state,
        cursorPosition: state.text.length,
      };
    }

    case 'set_text': {
      return {
        text: action.payload.text,
        cursorPosition: action.payload.cursorPosition ?? action.payload.text.length,
      };
    }

    case 'clear': {
      return {
        text: '',
        cursorPosition: 0,
      };
    }

    default:
      return state;
  }
}

export interface UseTextBufferOptions {
  initialValue?: string;
  onChange?: (value: string) => void;
}

export function useTextBuffer({ initialValue = '', onChange }: UseTextBufferOptions = {}) {
  const [state, dispatch] = useReducer(textBufferReducer, {
    text: initialValue,
    cursorPosition: initialValue.length,
  });

  const insert = useCallback((text: string) => {
    dispatch({ type: 'insert', payload: text });
    if (onChange) {
      const before = state.text.slice(0, state.cursorPosition);
      const after = state.text.slice(state.cursorPosition);
      onChange(before + text + after);
    }
  }, [state.text, state.cursorPosition, onChange]);

  const deleteBeforeCursor = useCallback(() => {
    dispatch({ type: 'delete_before' });
    if (onChange && state.cursorPosition > 0) {
      const before = state.text.slice(0, state.cursorPosition - 1);
      const after = state.text.slice(state.cursorPosition);
      onChange(before + after);
    }
  }, [state.text, state.cursorPosition, onChange]);

  const deleteAfterCursor = useCallback(() => {
    dispatch({ type: 'delete_after' });
    if (onChange && state.cursorPosition < state.text.length) {
      const before = state.text.slice(0, state.cursorPosition);
      const after = state.text.slice(state.cursorPosition + 1);
      onChange(before + after);
    }
  }, [state.text, state.cursorPosition, onChange]);

  const moveLeft = useCallback(() => {
    dispatch({ type: 'move_left' });
  }, []);

  const moveRight = useCallback(() => {
    dispatch({ type: 'move_right' });
  }, []);

  const moveToStart = useCallback(() => {
    dispatch({ type: 'move_start' });
  }, []);

  const moveToEnd = useCallback(() => {
    dispatch({ type: 'move_end' });
  }, []);

  const setText = useCallback((text: string, cursorPosition?: number) => {
    dispatch({ type: 'set_text', payload: { text, cursorPosition } });
    if (onChange) {
      onChange(text);
    }
  }, [onChange]);

  const clear = useCallback(() => {
    dispatch({ type: 'clear' });
    if (onChange) {
      onChange('');
    }
  }, [onChange]);

  return {
    text: state.text,
    cursorPosition: state.cursorPosition,
    insert,
    deleteBeforeCursor,
    deleteAfterCursor,
    moveLeft,
    moveRight,
    moveToStart,
    moveToEnd,
    setText,
    clear,
  };
}
