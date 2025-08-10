/**
 * Simple test to verify Jest configuration
 */

describe('Basic Jest Setup', () => {
  it('should run basic arithmetic test', () => {
    expect(2 + 2).toBe(4);
  });

  it('should handle string operations', () => {
    expect('hello' + ' world').toBe('hello world');
  });

  it('should work with arrays', () => {
    const arr = [1, 2, 3];
    expect(arr.length).toBe(3);
    expect(arr[0]).toBe(1);
  });
});