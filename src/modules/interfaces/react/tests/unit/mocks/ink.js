import React from 'react';

// Simple mocks for Ink components that return proper React elements (ESM)

export const Text = ({ children, ...props }) => {
  return React.createElement('Text', props, children);
};

export const Box = ({ children, ...props }) => {
  return React.createElement('Box', props, children);
};

export const Newline = () => React.createElement('Newline', {}, '\n');
export const Spacer = () => React.createElement('Spacer', {}, ' ');

// Static component: render list of items once at top; invoke render prop
export const Static = ({ items = [], children }) => {
  const content = Array.isArray(items)
    ? items.map((item, idx) => (typeof children === 'function' ? children(item, idx) : null))
    : null;
  return React.createElement(React.Fragment, {}, content);
};

// Mock hooks
export const useInput = (handler) => {
  global.__inkInputHandler = handler;
};

export const useStdin = () => ({
  stdin: { write: () => {} },
  isRawModeSupported: true
});

export const useStdout = () => ({
  stdout: { write: () => {}, columns: 80, rows: 24 }
});

export const useApp = () => ({
  exit: () => {}
});

export default { Text, Box, Newline, Spacer, Static, useInput, useStdin, useStdout, useApp };
