// Simple mock for ink-testing-library (ESM)
import React from 'react';

const extractTextContent = (element) => {
  if (typeof element === 'string') return element;
  if (typeof element === 'number') return String(element);
  if (!element) return '';
  
  if (Array.isArray(element)) {
    return element.map(extractTextContent).join('');
  }
  
  // Handle React elements
  if (React.isValidElement(element)) {
    // If this is a React.memo wrapper, render inner component
    try {
      const maybeMemo = element.type;
      if (maybeMemo && typeof maybeMemo === 'object' && 'type' in maybeMemo && typeof maybeMemo.type === 'function') {
        const inner = maybeMemo.type;
        const rendered = inner(element.props || {});
        return extractTextContent(rendered);
      }
    } catch {}

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
      
      // Return children or type name as fallback for components without explicit text
      if (['Text', 'Box', 'MockComponent'].includes(typeName)) {
        return element.props?.children ? extractTextContent(element.props.children) : '';
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
    unmount: () => {},
    rerender: (newComponent) => {
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
    }
  };
};

export { render };
export default { render };
