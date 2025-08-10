// Simple mock for ink-testing-library
const React = require('react');

const extractTextContent = (element) => {
  if (typeof element === 'string') return element;
  if (typeof element === 'number') return String(element);
  if (!element) return '';
  
  if (Array.isArray(element)) {
    return element.map(extractTextContent).join('');
  }
  
  // Handle React elements
  if (React.isValidElement(element)) {
    // Extract children first
    if (element.props && element.props.children) {
      return extractTextContent(element.props.children);
    }
    
    // Handle components with various text props
    const textProps = ['text', 'placeholder', 'label', 'title', 'value'];
    for (const prop of textProps) {
      if (element.props && element.props[prop]) {
        return String(element.props[prop]);
      }
    }
    
    // Handle specific component types
    if (element.type) {
      const typeName = typeof element.type === 'string' ? element.type : 
                       element.type.name || element.type.displayName || '';
      
      // Return type name as fallback for components without text
      if (['Text', 'Box', 'MockComponent'].includes(typeName)) {
        return element.props?.children ? extractTextContent(element.props.children) : typeName;
      }
    }
    
    return '';
  }
  
  // Handle plain objects with props
  if (element && typeof element === 'object') {
    if (element.props && element.props.children) {
      return extractTextContent(element.props.children);
    }
    if (element.children) {
      return extractTextContent(element.children);
    }
  }
  
  return '';
};

const render = (component) => {
  let lastFrameContent = '';
  const frames = [];

  const stdin = {
    write: (data) => {
      if (global.__inkInputHandler) {
        const key = data === '\x1b' ? { escape: true } : {};
        global.__inkInputHandler(data, key);
      }
    }
  };

  // Try to render the component and extract text content
  try {
    // If it's a React element, try to render it
    if (React.isValidElement(component)) {
      // If the element's type is a function, try to call it
      if (typeof component.type === 'function') {
        try {
          const rendered = component.type(component.props || {});
          lastFrameContent = extractTextContent(rendered);
        } catch (funcError) {
          // Fallback to extracting from the element itself
          lastFrameContent = extractTextContent(component);
        }
      } else {
        lastFrameContent = extractTextContent(component);
      }
    } else if (typeof component === 'function') {
      // If it's a function component, call it with empty props
      const rendered = component({});
      lastFrameContent = extractTextContent(rendered);
    } else {
      // Fallback to direct text extraction
      lastFrameContent = extractTextContent(component);
    }
  } catch (error) {
    console.warn('Mock render error:', error);
    lastFrameContent = '';
  }

  frames.push(lastFrameContent);

  return {
    lastFrame: () => lastFrameContent,
    frames,
    stdin,
    unmount: jest.fn(),
    rerender: jest.fn((newComponent) => {
      try {
        if (React.isValidElement(newComponent)) {
          lastFrameContent = extractTextContent(newComponent);
        } else if (typeof newComponent === 'function') {
          const rendered = newComponent({});
          lastFrameContent = extractTextContent(rendered);
        } else {
          lastFrameContent = extractTextContent(newComponent);
        }
        frames.push(lastFrameContent);
      } catch (error) {
        console.warn('Mock rerender error:', error);
      }
    })
  };
};

module.exports = { render };