import { afterEach, expect, it, vi } from 'vitest';
import { downloadResumeDocx } from '@/lib/api/resume';
import { DEFAULT_TEMPLATE_SETTINGS } from '@/lib/types/template-settings';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('downloads Word with the session, selected page size and margins', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(['word-content'])));
  vi.stubGlobal('fetch', fetchMock);
  const blob = await downloadResumeDocx('member-resume', {
    ...DEFAULT_TEMPLATE_SETTINGS,
    pageSize: 'LETTER',
  });
  expect(blob.size).toBeGreaterThan(0);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toContain('/api/v1/resumes/member-resume/docx?');
  expect(url).toContain('pageSize=LETTER');
  expect(url).toContain('marginTop=10');
  expect(url).toContain('fontSize=3');
  expect(url).toContain('headerFont=serif');
  expect(url).toContain('bodyFont=sans-serif');
  expect(url).toContain('sectionSpacing=3');
  expect(url).toContain('lineHeight=3');
  expect(options.credentials).toBe('include');
});

it('reports a denied or missing Word document instead of downloading an error', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('Resume not found', { status: 404 }))
  );
  await expect(downloadResumeDocx('other-owner')).rejects.toThrow('status 404');
});

it('uses saved editor formatting when downloaded from the resume viewer', async () => {
  localStorage.setItem(
    'resume_builder_settings',
    JSON.stringify({
      margins: { left: 15 },
      fontSize: { base: 4, headerFont: 'mono' },
      compactMode: true,
    })
  );
  const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(['word-content'])));
  vi.stubGlobal('fetch', fetchMock);
  try {
    await downloadResumeDocx('member-resume');
    expect(fetchMock.mock.calls[0][0]).toContain('marginLeft=15');
    expect(fetchMock.mock.calls[0][0]).toContain('fontSize=4');
    expect(fetchMock.mock.calls[0][0]).toContain('headerFont=mono');
    expect(fetchMock.mock.calls[0][0]).toContain('compactMode=true');
  } finally {
    localStorage.removeItem('resume_builder_settings');
  }
});
