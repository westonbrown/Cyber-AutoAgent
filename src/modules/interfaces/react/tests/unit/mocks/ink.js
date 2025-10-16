import React from 'react';

const toNumber = (value) => (typeof value === 'number' ? value : Number(value));

const extractStyleProps = (props = {}) => {
  const style = {};

  const assign = (prop, cssProp, transform = (v) => v) => {
    if (props[prop] !== undefined) {
      style[cssProp] = transform(props[prop]);
      delete props[prop];
    }
  };

  assign('flexDirection', 'flexDirection');
  if (style.flexDirection) {
    style.display = 'flex';
  }
  ['alignItems', 'justifyContent', 'gap'].forEach((prop) => assign(prop, prop));

  ['marginTop', 'marginBottom', 'marginLeft', 'marginRight', 'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight'].forEach((prop) =>
    assign(prop, prop, toNumber)
  );

  if (props.marginX !== undefined) {
    const value = toNumber(props.marginX);
    style.marginLeft = style.marginRight = value;
    delete props.marginX;
  }
  if (props.marginY !== undefined) {
    const value = toNumber(props.marginY);
    style.marginTop = style.marginBottom = value;
    delete props.marginY;
  }
  if (props.paddingX !== undefined) {
    const value = toNumber(props.paddingX);
    style.paddingLeft = style.paddingRight = value;
    delete props.paddingX;
  }
  if (props.paddingY !== undefined) {
    const value = toNumber(props.paddingY);
    style.paddingTop = style.paddingBottom = value;
    delete props.paddingY;
  }

  ['width', 'height', 'maxWidth', 'minWidth'].forEach((prop) => assign(prop, prop));

  if (props.borderStyle === 'round') {
    style.border = style.border || '1px solid #555';
    style.borderRadius = 8;
    delete props.borderStyle;
  }
  if (props.borderColor) {
    style.border = `1px solid ${props.borderColor}`;
    delete props.borderColor;
  }

  return style;
};

const applyTextDecorations = (props, style) => {
  if (props.color) {
    style.color = props.color;
    delete props.color;
  }
  if (props.dimColor) {
    style.opacity = 0.75;
    delete props.dimColor;
  }
  if (props.bold) {
    style.fontWeight = 'bold';
    delete props.bold;
  }
  if (props.backgroundColor) {
    style.backgroundColor = props.backgroundColor;
    delete props.backgroundColor;
  }
};

export const Text = ({ children, ...props }) => {
  const style = extractStyleProps(props);
  applyTextDecorations(props, style);
  return React.createElement('span', { style }, children);
};

export const Box = ({ children, ...props }) => {
  const style = extractStyleProps(props);
  return React.createElement('div', { style }, children);
};

export const Newline = () => React.createElement('br');
export const Spacer = () => React.createElement('span', { style: { display: 'inline-block', width: '1ch' } }, ' ');

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
