import { ExecutionMode } from '../../../src/services/ExecutionService.js';
import {
  ExecutionServiceSelectionError,
  RejectedServiceInfo
} from '../../../src/services/ExecutionServiceFactory.js';

describe('ExecutionServiceSelectionError', () => {
  it('formats detailed diagnostics for rejected execution modes', () => {
    const attempts: RejectedServiceInfo[] = [
      {
        mode: ExecutionMode.DOCKER_STACK,
        reason: 'Docker image cyber-autoagent:latest not found',
        issues: [
          {
            type: 'docker',
            severity: 'error',
            message: 'cyber-autoagent:latest image is missing',
            suggestion: 'Run `docker compose build` before starting the UI'
          }
        ],
        warnings: ['Ensure Docker Desktop (or daemon) is running']
      },
      {
        mode: ExecutionMode.PYTHON_CLI,
        reason: 'Service creation failed',
        errorMessage: 'Python 3.10+ not available'
      }
    ];

    const error = new ExecutionServiceSelectionError(
      [ExecutionMode.DOCKER_STACK, ExecutionMode.PYTHON_CLI],
      attempts
    );

    expect(error.message).toContain('No execution service available');
    expect(error.diagnostics).toHaveLength(2);

    const firstDiagnostics = error.diagnostics[0];
    expect(firstDiagnostics).toContain('Full Stack');
    expect(firstDiagnostics).toContain('cyber-autoagent:latest image is missing');
    expect(firstDiagnostics).toContain('docker compose build');

    const secondDiagnostics = error.diagnostics[1];
    expect(secondDiagnostics).toContain('Local CLI');
    expect(secondDiagnostics).toContain('Python 3.10+ not available');
  });
});
