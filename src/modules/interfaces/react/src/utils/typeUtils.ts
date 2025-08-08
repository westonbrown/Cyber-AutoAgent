/**
 * Type utilities for consistent type checking and data manipulation
 */

/**
 * Check if a value is a non-empty string
 */
export const isNonEmptyString = (value: unknown): value is string => {
  return typeof value === 'string' && value.trim().length > 0;
};

/**
 * Check if a value is a valid object (not null, not array)
 */
export const isObject = (value: unknown): value is Record<string, unknown> => {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
};

/**
 * Safely convert any value to string
 */
export const toSafeString = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

/**
 * Truncate string with ellipsis
 */
export const truncate = (str: string, maxLength: number): string => {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength) + '...';
};

/**
 * Safely get nested property from object
 */
export const getNestedValue = <T = unknown>(
  obj: Record<string, unknown>,
  path: string,
  defaultValue?: T
): T | undefined => {
  const keys = path.split('.');
  let current: any = obj;
  
  for (const key of keys) {
    if (current?.[key] === undefined) {
      return defaultValue;
    }
    current = current[key];
  }
  
  return current as T;
};

/**
 * Deep merge objects (non-mutating)
 */
export const deepMerge = <T extends Record<string, any>>(
  target: T,
  ...sources: Partial<T>[]
): T => {
  if (!sources.length) return target;
  
  const result = { ...target };
  
  for (const source of sources) {
    if (!isObject(source)) continue;
    
    for (const key in source) {
      const sourceValue = source[key];
      const targetValue = result[key];
      
      if (isObject(sourceValue) && isObject(targetValue)) {
        result[key] = deepMerge(targetValue as any, sourceValue as any);
      } else {
        result[key] = sourceValue as any;
      }
    }
  }
  
  return result;
};

/**
 * Check if value is a promise
 */
export const isPromise = <T = unknown>(value: unknown): value is Promise<T> => {
  return value instanceof Promise || 
    (value !== null && 
     typeof value === 'object' && 
     'then' in value && 
     typeof (value as any).then === 'function');
};

/**
 * Debounce function execution
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

/**
 * Throttle function execution
 */
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle = false;
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => { inThrottle = false; }, limit);
    }
  };
};