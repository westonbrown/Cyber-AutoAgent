/**
 * StreamDisplay path resolution tests (no Ink render)
 *
 * Focus:
 * - getReportPathCandidates uses outputBaseDir when provided
 * - Container-relative /app/outputs paths are mapped into host outputDir
 */

import { describe, it, expect, beforeAll } from '@jest/globals';

let getReportPathCandidates: any;
let mapContainerReportPath: any;

beforeAll(async () => {
  const mod = await import('../../../dist/components/StreamDisplay.js');
  getReportPathCandidates = mod.getReportPathCandidates;
  mapContainerReportPath = mod.mapContainerReportPath;
});

describe('StreamDisplay report paths', () => {
  it('uses outputBaseDir to construct unified report path for operation', () => {
    const ctx = {
      operationId: 'OP_123',
      target: 'https://example.com',
    };
    const outputBaseDir = '/tmp/cyber-outputs';

    const candidates: string[] = getReportPathCandidates(
      ctx,
      null,
      null,
      outputBaseDir,
    );

    // We expect at least one candidate under outputBaseDir with the operation id
    expect(
      candidates.some(p =>
        p.startsWith(outputBaseDir) &&
        p.includes('OP_123') &&
        p.endsWith('security_assessment_report.md')
      ),
    ).toBe(true);
  });

  it('prefers outputBaseDir when resolving relative reportPath', () => {
    const ctx = {
      operationId: 'OP_999',
      target: 'https://example.com',
    };
    const outputBaseDir = '/tmp/cyber-outputs';

    const candidates: string[] = getReportPathCandidates(
      ctx,
      'relative/report.md',
      null,
      outputBaseDir,
    );

    expect(
      candidates.some(p => p === `${outputBaseDir}/relative/report.md` || p === `${outputBaseDir}\relative\report.md`)
    ).toBe(true);
  });

  it('maps /app/outputs container path into host outputDir', () => {
    const hostDir = '/host/outputs';
    const raw = '/app/outputs/test-target/OP_1/security_assessment_report.md';

    const mapped = mapContainerReportPath(raw, hostDir);

    expect(mapped).toBe(
      `${hostDir}/test-target/OP_1/security_assessment_report.md` ||
      `${hostDir}\\test-target\\OP_1\\security_assessment_report.md`
    );
  });

  it('is idempotent for non-container paths', () => {
    const hostDir = '/host/outputs';
    const raw = '/other/path/report.md';

    const mapped = mapContainerReportPath(raw, hostDir);
    expect(mapped).toBe(raw);
  });
});