/**
 * Mock for yaml module
 * Used in tests to parse YAML content
 */

export const parse = (str) => {
  try {
    // Simple YAML parsing for test purposes
    return JSON.parse(str);
  } catch {
    return {};
  }
};

export const stringify = (obj) => {
  return JSON.stringify(obj, null, 2);
};

export default {
  parse,
  stringify
};
