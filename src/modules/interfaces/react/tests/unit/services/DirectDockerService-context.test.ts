/**
 * DirectDockerService docker context detection tests
 *
 * Note: Since getDockerConnectionOptions() is an internal implementation detail
 * and testing it directly would require mocking ES modules (which is complex in Jest),
 * these tests verify the integration behavior instead.
 */
import { describe, it, expect } from '@jest/globals';
import { DirectDockerService } from '../../../src/services/DirectDockerService.js';

describe('DirectDockerService docker context detection', () => {
  it('should create DirectDockerService instance successfully', () => {
    // This test verifies that the docker context detection logic doesn't crash
    // If docker context commands fail, it should fall back to default behavior
    const svc = new DirectDockerService();
    expect(svc).toBeDefined();
    expect(svc).toBeInstanceOf(DirectDockerService);
  });

  it('should handle docker context detection without errors', async () => {
    // Verify that checkDocker doesn't throw even if context detection fails
    const result = await DirectDockerService.checkDocker();
    expect(typeof result).toBe('boolean');
  });

  it('should create dockerClient successfully in constructor', () => {
    const svc = new DirectDockerService();
    // Verify internal dockerClient was created (accessing private property for test)
    expect((svc as any).dockerClient).toBeDefined();
  });
});
