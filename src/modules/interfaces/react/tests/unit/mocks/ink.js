const React = require('react');

// Simple mocks for Ink components that return proper React elements

const Text = ({ children, ...props }) => {
  return React.createElement('Text', props, children);
};

const Box = ({ children, ...props }) => {
  return React.createElement('Box', props, children);
};

const Newline = () => React.createElement('Newline', {}, '\n');
const Spacer = () => React.createElement('Spacer', {}, ' ');

// Mock hooks
const useInput = (handler) => {
  global.__inkInputHandler = handler;
};

const useStdin = () => ({
  stdin: { write: jest.fn() },
  isRawModeSupported: true
});

const useStdout = () => ({
  stdout: { write: jest.fn(), columns: 80, rows: 24 }
});

const useApp = () => ({
  exit: jest.fn()
});

module.exports = {
  Text,
  Box,
  Newline,
  Spacer,
  useInput,
  useStdin,
  useStdout,
  useApp
};