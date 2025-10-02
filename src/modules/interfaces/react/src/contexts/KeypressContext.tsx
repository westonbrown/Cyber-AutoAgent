/**
 * KeypressContext - Custom keypress handling with proper bracketed paste support
 * Inspired by gemini-cli's implementation
 *
 * This replaces Ink's useInput to handle paste properly at the stdin level
 */

import React, { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import { useStdin } from 'ink';
import readline from 'node:readline';
import { PassThrough } from 'node:stream';

const ESC = '\u001B';
export const PASTE_MODE_PREFIX = `${ESC}[200~`;
export const PASTE_MODE_SUFFIX = `${ESC}[201~`;
export const PASTE_DETECTION_TIMEOUT_MS = 100; // Detect rapid input as paste

export interface Key {
  name: string;
  ctrl: boolean;
  meta: boolean;
  shift: boolean;
  paste: boolean;
  sequence: string;
}

export type KeypressHandler = (key: Key) => void;

interface KeypressContextValue {
  subscribe: (handler: KeypressHandler) => void;
  unsubscribe: (handler: KeypressHandler) => void;
}

const KeypressContext = createContext<KeypressContextValue | undefined>(undefined);

export function useKeypressContext() {
  const context = useContext(KeypressContext);
  if (!context) {
    throw new Error('useKeypressContext must be used within a KeypressProvider');
  }
  return context;
}

export function KeypressProvider({ children }: { children: React.ReactNode }) {
  const { stdin, setRawMode } = useStdin();
  const subscribers = useRef<Set<KeypressHandler>>(new Set()).current;

  const subscribe = useCallback(
    (handler: KeypressHandler) => {
      subscribers.add(handler);
    },
    [subscribers]
  );

  const unsubscribe = useCallback(
    (handler: KeypressHandler) => {
      subscribers.delete(handler);
    },
    [subscribers]
  );

  useEffect(() => {
    const wasRaw = stdin.isRaw;
    if (wasRaw === false) {
      setRawMode(true);
    }

    const keypressStream = new PassThrough();
    let isPaste = false;
    let pasteBuffer = Buffer.alloc(0);
    let rapidInputBuffer = '';
    let rapidInputTimer: NodeJS.Timeout | null = null;

    const broadcast = (key: Key) => {
      for (const handler of subscribers) {
        handler(key);
      }
    };

    const clearRapidInputTimer = () => {
      if (rapidInputTimer) {
        clearTimeout(rapidInputTimer);
        rapidInputTimer = null;
      }
    };

    const handleKeypress = (_: unknown, key: Key) => {
      // Handle paste-start marker (bracketed paste)
      if (key.name === 'paste-start') {
        isPaste = true;
        clearRapidInputTimer(); // Cancel rapid input detection
        return;
      }

      // Handle paste-end marker (bracketed paste) - send accumulated paste as single event
      if (key.name === 'paste-end') {
        isPaste = false;
        broadcast({
          name: '',
          ctrl: false,
          meta: false,
          shift: false,
          paste: true,
          sequence: pasteBuffer.toString(),
        });
        pasteBuffer = Buffer.alloc(0);
        return;
      }

      // Accumulate bracketed paste data
      if (isPaste) {
        pasteBuffer = Buffer.concat([pasteBuffer, Buffer.from(key.sequence)]);
        return;
      }

      // Detect rapid multi-character input (Cmd+V without bracketed paste)
      // Inspired by gemini-cli's drag detection
      if (key.sequence && key.sequence.length > 1 && !key.ctrl && !key.meta && !key.name) {
        // Start accumulating rapid input
        rapidInputBuffer += key.sequence;
        clearRapidInputTimer();

        rapidInputTimer = setTimeout(() => {
          const seq = rapidInputBuffer;
          rapidInputBuffer = '';
          if (seq) {
            broadcast({ ...key, name: '', paste: true, sequence: seq });
          }
        }, PASTE_DETECTION_TIMEOUT_MS);

        return;
      }

      // If we have pending rapid input, flush it first
      if (rapidInputBuffer) {
        clearRapidInputTimer();
        const seq = rapidInputBuffer;
        rapidInputBuffer = '';
        broadcast({ ...key, name: '', paste: true, sequence: seq });
        // Then process current key normally below
      }

      // Normal keypress - broadcast directly
      broadcast({ ...key, paste: false });
    };

    const handleRawKeypress = (data: Buffer) => {
      const pasteModePrefixBuffer = Buffer.from(PASTE_MODE_PREFIX);
      const pasteModeSuffixBuffer = Buffer.from(PASTE_MODE_SUFFIX);

      let pos = 0;
      while (pos < data.length) {
        const prefixPos = data.indexOf(pasteModePrefixBuffer, pos);
        const suffixPos = data.indexOf(pasteModeSuffixBuffer, pos);
        const isPrefixNext = prefixPos !== -1 && (suffixPos === -1 || prefixPos < suffixPos);
        const isSuffixNext = suffixPos !== -1 && (prefixPos === -1 || suffixPos < prefixPos);

        let nextMarkerPos = -1;
        let markerLength = 0;

        if (isPrefixNext) {
          nextMarkerPos = prefixPos;
          markerLength = pasteModePrefixBuffer.length;
        } else if (isSuffixNext) {
          nextMarkerPos = suffixPos;
          markerLength = pasteModeSuffixBuffer.length;
        }

        if (nextMarkerPos === -1) {
          keypressStream.write(data.slice(pos));
          return;
        }

        const nextData = data.slice(pos, nextMarkerPos);
        if (nextData.length > 0) {
          keypressStream.write(nextData);
        }

        const createPasteKeyEvent = (name: 'paste-start' | 'paste-end'): Key => ({
          name,
          ctrl: false,
          meta: false,
          shift: false,
          paste: false,
          sequence: '',
        });

        if (isPrefixNext) {
          handleKeypress(undefined, createPasteKeyEvent('paste-start'));
        } else if (isSuffixNext) {
          handleKeypress(undefined, createPasteKeyEvent('paste-end'));
        }

        pos = nextMarkerPos + markerLength;
      }
    };

    const rl = readline.createInterface({
      input: keypressStream,
      escapeCodeTimeout: 0,
    });

    readline.emitKeypressEvents(keypressStream, rl);
    keypressStream.on('keypress', handleKeypress);
    stdin.on('data', handleRawKeypress);

    return () => {
      keypressStream.removeListener('keypress', handleKeypress);
      stdin.removeListener('data', handleRawKeypress);
      rl.close();

      if (wasRaw === false) {
        setRawMode(false);
      }

      // Flush any pending bracketed paste data
      if (isPaste) {
        broadcast({
          name: '',
          ctrl: false,
          meta: false,
          shift: false,
          paste: true,
          sequence: pasteBuffer.toString(),
        });
        pasteBuffer = Buffer.alloc(0);
      }

      // Flush any pending rapid input data
      clearRapidInputTimer();
      if (rapidInputBuffer) {
        broadcast({
          name: '',
          ctrl: false,
          meta: false,
          shift: false,
          paste: true,
          sequence: rapidInputBuffer,
        });
        rapidInputBuffer = '';
      }
    };
  }, [stdin, setRawMode, subscribers]);

  return (
    <KeypressContext.Provider value={{ subscribe, unsubscribe }}>
      {children}
    </KeypressContext.Provider>
  );
}
