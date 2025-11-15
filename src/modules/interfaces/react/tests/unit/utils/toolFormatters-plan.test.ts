import { describe, it, expect } from '@jest/globals';

describe('TOON plan preview helper', () => {
  it('parses plan_overview blocks into readable preview', async () => {
    const mod: any = await import('../../../src/utils/toolFormatters.js');
    const { getToonPlanPreview } = mod;

    const content = `plan_overview[1]{objective,current_phase,total_phases}:
  Harden payments portal,2,3
plan_phases[3]{id,title,status,criteria}:
  1,Recon,done,map services
  2,Testing,active,validate IDOR
  3,Exploit,pending,extract flag`;

    const preview = getToonPlanPreview(content);
    expect(preview).toContain('Harden payments portal');
    expect(preview).toContain('Phase 2/3');
    expect(preview).toContain('Testing');
  });

  it('returns null for non-plan content', async () => {
    const mod: any = await import('../../../src/utils/toolFormatters.js');
    const { getToonPlanPreview } = mod;
    expect(getToonPlanPreview('random note')).toBeNull();
  });
});
