const React = require('react');

// Generic mock for all ink-* components that returns proper React elements
const MockComponent = ({ children, ...props }) => {
  const content = children || props.text || props.placeholder || '';
  return React.createElement('MockComponent', props, content);
};

module.exports = MockComponent;
module.exports.default = MockComponent;