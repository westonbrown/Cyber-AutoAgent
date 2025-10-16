export type RawEnvironmentValue =
  | string
  | number
  | boolean
  | null
  | RawEnvironmentValue[]
  | { [key: string]: RawEnvironmentValue };

export type RawEnvironmentMap = Record<string, RawEnvironmentValue>;

const sanitizeKey = (key: string): string => {
  return key
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .toUpperCase();
};

/**
 * Flatten an arbitrary environment configuration object into a
 * uppercase KEY=value map suitable for process environments.
 */
export function flattenEnvironment(environment?: RawEnvironmentMap | null): Record<string, string> {
  const result: Record<string, string> = {};

  if (!environment || typeof environment !== 'object') {
    return result;
  }

  const processEntry = (value: RawEnvironmentValue, path: string[]) => {
    if (value === null || value === undefined) {
      return;
    }

    if (Array.isArray(value)) {
      // stringify arrays to preserve structure
      const finalKey = path.join('_');
      if (!finalKey) return;
      result[finalKey] = JSON.stringify(value);
      return;
    }

    if (typeof value === 'object') {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return;
      }
      for (const [childKey, childValue] of entries) {
        const sanitizedChild = sanitizeKey(childKey);
        if (!sanitizedChild) continue;
        processEntry(childValue, [...path, sanitizedChild]);
      }
      return;
    }

    const finalKey = path.join('_');
    if (!finalKey) {
      return;
    }

    let stringValue: string;
    if (typeof value === 'boolean') {
      stringValue = value ? 'true' : 'false';
    } else {
      stringValue = String(value);
    }

    result[finalKey] = stringValue;
  };

  for (const [rawKey, rawValue] of Object.entries(environment)) {
    if (rawValue === undefined) continue;
    const key = sanitizeKey(rawKey);
    if (!key) continue;
    processEntry(rawValue, [key]);
  }

  return result;
}

