import React from 'react';

// Generic mock for all ink-* components; provide ESM default export
const MockComponent = ({ children, ...props }) => {
  const content = children || props.text || props.placeholder || '';
  return React.createElement('MockComponent', props, content);
};

export default MockComponent;
