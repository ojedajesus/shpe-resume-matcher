import { describe, expect, it } from 'vitest';
import { compareRequirements } from '@/lib/utils/requirement-evidence';

describe('grounded requirement comparison', () => {
  it('distinguishes priority and quotes only verbatim evidence', () => {
    const evidence = [
      'Build Python APIs for student scheduling.',
      'Used Docker in a class project.',
    ];
    const result = compareRequirements(
      'Required: Build Python APIs.\nKubernetes preferred.\nAWS certification required.',
      evidence
    );
    expect(result[0]).toMatchObject({
      priority: 'required',
      status: 'supported',
      evidence: evidence[0],
    });
    expect(result[1]).toMatchObject({ priority: 'preferred', status: 'not evidenced' });
    expect(result[2].evidence).toBeUndefined();
  });
});
