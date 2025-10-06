/**
 * Mock for js-yaml module
 * Used in tests to parse YAML content
 */

export const load = (str) => {
  try {
    // Simple YAML parsing for test purposes
    return JSON.parse(str);
  } catch {
    return {};
  }
};

export const dump = (obj) => {
  return JSON.stringify(obj, null, 2);
};

export default {
  load,
  dump
};
