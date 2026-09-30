export type RequirementEvidence = {
  requirement: string;
  priority: 'required' | 'preferred';
  status: 'supported' | 'needs detail' | 'not evidenced';
  evidence?: string;
};

const WORD = /[a-z0-9+#.]{3,}/gi;
const STOP = new Set([
  'and',
  'the',
  'with',
  'for',
  'from',
  'that',
  'this',
  'you',
  'our',
  'will',
  'are',
]);
const words = (text: string) =>
  new Set(
    (text.match(WORD) ?? []).map((word) => word.toLowerCase()).filter((word) => !STOP.has(word))
  );

/** Deterministic and quote-grounded: it never generates or rewrites member evidence. */
export function compareRequirements(job: string, evidenceLines: string[]): RequirementEvidence[] {
  const candidates = job
    .split(/\n|(?<=[.!?])\s+/)
    .map((line) => line.replace(/^[-*•\s]+/, '').trim())
    .filter((line) => line.length >= 12);
  return candidates.slice(0, 24).map((requirement) => {
    const priority = /preferred|nice to have|plus|bonus|ideally/i.test(requirement)
      ? 'preferred'
      : 'required';
    const requiredWords = words(requirement);
    let best: { line: string; count: number } | undefined;
    for (const line of evidenceLines) {
      const lineWords = words(line);
      const count = [...requiredWords].filter((word) => lineWords.has(word)).length;
      if (!best || count > best.count) best = { line, count };
    }
    const status =
      best && best.count >= 2
        ? 'supported'
        : best && best.count === 1
          ? 'needs detail'
          : 'not evidenced';
    return {
      requirement,
      priority,
      status,
      evidence: status === 'supported' ? best?.line : undefined,
    };
  });
}
