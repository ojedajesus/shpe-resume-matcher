import { createHmac, timingSafeEqual } from 'node:crypto';
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

export const runtime = 'nodejs';
export const maxDuration = 120;

function authorized(body: string, signature: string, secret: string): boolean {
  if (!/^[a-f0-9]{64}$/.test(signature)) return false;
  const expected = createHmac('sha256', secret).update(body).digest();
  return timingSafeEqual(expected, Buffer.from(signature, 'hex'));
}

/** Internal renderer. Only the backend may request a scoped print-page PDF. */
export async function POST(request: Request): Promise<Response> {
  const secret = process.env.PDF_RENDERER_SECRET;
  if (!secret) return new Response('Renderer not configured', { status: 503 });
  const body = await request.text();
  if (body.length > 16_384) return new Response('Request too large', { status: 413 });
  if (!authorized(body, request.headers.get('x-render-signature') || '', secret)) {
    return new Response('Unauthorized', { status: 401 });
  }
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    return new Response('Invalid request', { status: 400 });
  }
  const { url, pageSize = 'A4', selector = '.resume-print', margins = {}, timestamp } = payload;
  if (typeof timestamp !== 'number' || Math.abs(Date.now() / 1000 - timestamp) > 120) {
    return new Response('Expired request', { status: 401 });
  }
  let target: URL;
  try {
    target = new URL(url);
  } catch {
    return new Response('Invalid URL', { status: 400 });
  }
  const origin = new URL(process.env.PDF_RENDER_ORIGIN || request.url).origin;
  if (
    target.origin !== origin ||
    target.username ||
    target.password ||
    !/^\/print\/(resumes|cover-letter)\/[a-zA-Z0-9_-]+$/.test(target.pathname) ||
    !target.searchParams.get('renderToken') ||
    !['A4', 'LETTER'].includes(pageSize) ||
    !['.resume-print', '.cover-letter-print', '.resume-print, [data-print-error]'].includes(
      selector
    )
  ) {
    return new Response('Invalid print target', { status: 400 });
  }
  const pdfMargins: Record<string, string> = {};
  for (const side of ['top', 'right', 'bottom', 'left']) {
    const value = Number(margins[side] ?? 10);
    if (!Number.isFinite(value) || value < 0 || value > 30) {
      return new Response('Invalid margin', { status: 400 });
    }
    pdfMargins[side] = `${value}mm`;
  }
  let browser;
  try {
    browser = await puppeteer.launch({
      args: chromium.args.filter((argument) => argument !== '--single-process'),
      pipe: true,
      executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || (await chromium.executablePath()),
      headless: true,
    });
    const page = await browser.newPage();
    // An optional Vercel protection bypass is server-only and sent only to
    // this deployment's origin, never to external image/font requests.
    const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
    if (bypass) {
      await page.setRequestInterception(true);
      page.on('request', (resource) => {
        const headers = { ...resource.headers() };
        if (new URL(resource.url()).origin === origin) {
          headers['x-vercel-protection-bypass'] = bypass;
        }
        void resource.continue({ headers });
      });
    }
    const response = await page.goto(target.href, { waitUntil: 'load', timeout: 60_000 });
    if (!response?.ok()) throw new Error('Print page unavailable');
    await page.waitForSelector(selector, { timeout: 30_000 });
    if (await page.$('[data-print-error]')) throw new Error('Print data unavailable');
    await page.waitForFunction(() => document.fonts.status === 'loaded', { timeout: 30_000 });
    await page.emulateMediaType('print');
    const pdf = await page.pdf({
      format: pageSize === 'LETTER' ? 'Letter' : 'A4',
      printBackground: true,
      margin: pdfMargins,
    });
    return new Response(new Uint8Array(pdf), {
      headers: { 'Content-Type': 'application/pdf', 'Cache-Control': 'private, no-store' },
    });
  } catch {
    // Do not log URLs: they carry short-lived authorization and resume IDs.
    return new Response('PDF rendering failed', { status: 503 });
  } finally {
    await browser?.close();
  }
}
