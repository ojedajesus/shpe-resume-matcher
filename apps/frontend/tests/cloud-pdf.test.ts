// @vitest-environment node
import { createHmac } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ launch: vi.fn() }));
vi.mock('puppeteer-core', () => ({ default: { launch: mocks.launch } }));
vi.mock('@sparticuz/chromium', () => ({
  default: { args: [], executablePath: vi.fn().mockResolvedValue('/synthetic/chromium') },
}));
import { POST } from '@/app/internal/pdf/route';

function request(payload: object, secret = 'synthetic-secret'): Request {
  const body = JSON.stringify(payload);
  return new Request('https://frontend.example.test/internal/pdf', {
    method: 'POST',
    body,
    headers: { 'x-render-signature': createHmac('sha256', secret).update(body).digest('hex') },
  });
}
const payload = () => ({
  url: 'https://frontend.example.test/print/resumes/resume-id?renderToken=fake',
  timestamp: Date.now() / 1000,
  pageSize: 'LETTER',
  margins: { top: 12 },
});

describe('cloud PDF renderer security and output', () => {
  beforeEach(() => {
    vi.stubEnv('PDF_RENDERER_SECRET', 'synthetic-secret');
    mocks.launch.mockReset();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });
  it('rejects unsigned, expired and external targets before launching Chromium', async () => {
    expect((await POST(request(payload(), 'wrong'))).status).toBe(401);
    expect((await POST(request({ ...payload(), timestamp: 1 }))).status).toBe(401);
    expect(
      (await POST(request({ ...payload(), url: 'http://169.254.169.254/latest/meta-data' }))).status
    ).toBe(400);
    expect(
      (await POST(request({ ...payload(), url: 'https://frontend.example.test/api/v1/config' })))
        .status
    ).toBe(400);
    expect(mocks.launch).not.toHaveBeenCalled();
  });
  it('prints the authorized page and closes the browser', async () => {
    const page = {
      goto: vi.fn().mockResolvedValue({ ok: () => true }),
      waitForSelector: vi.fn(),
      $: vi.fn().mockResolvedValue(null),
      evaluate: vi.fn(),
      waitForFunction: vi.fn(),
      emulateMediaType: vi.fn(),
      pdf: vi.fn().mockResolvedValue(new TextEncoder().encode('%PDF-1.7\nsynthetic')),
    };
    const close = vi.fn();
    mocks.launch.mockResolvedValue({ newPage: async () => page, close });
    const response = await POST(request(payload()));
    expect(response.status).toBe(200);
    expect(await response.text()).toContain('%PDF-');
    expect(page.pdf).toHaveBeenCalledWith(
      expect.objectContaining({
        format: 'Letter',
        margin: expect.objectContaining({ top: '12mm' }),
      })
    );
    expect(close).toHaveBeenCalledOnce();
  });
  it('does not return a PDF when the print page reports missing data', async () => {
    const close = vi.fn();
    mocks.launch.mockResolvedValue({
      newPage: async () => ({
        goto: async () => ({ ok: () => true }),
        waitForSelector: vi.fn(),
        $: async () => ({}),
      }),
      close,
    });
    expect((await POST(request(payload()))).status).toBe(503);
    expect(close).toHaveBeenCalledOnce();
  });
});
