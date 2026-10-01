import type { Metadata } from 'next';
import { Geist, Noto_Sans_JP, Noto_Sans_KR, Noto_Sans_SC, Space_Grotesk } from 'next/font/google';
import './(default)/css/globals.css';

const spaceGrotesk = Space_Grotesk({
  variable: '--font-space-grotesk',
  subsets: ['latin'],
  display: 'swap',
});

const geist = Geist({
  variable: '--font-geist',
  subsets: ['latin'],
  display: 'swap',
});

// CJK fallbacks for Chinese/Japanese/Korean resume content. These declarations
// intentionally match upstream: next/font emits genuine browser-served font
// faces and the per-locale ordering remains in template-settings.ts.
const notoSansSC = Noto_Sans_SC({
  variable: '--font-noto-sans-sc',
  display: 'swap',
  preload: false,
});

const notoSansKR = Noto_Sans_KR({
  variable: '--font-noto-sans-kr',
  display: 'swap',
  preload: false,
});

const notoSansJP = Noto_Sans_JP({
  variable: '--font-noto-sans-jp',
  display: 'swap',
  preload: false,
});

export const metadata: Metadata = {
  title: 'SHPE Resume Matcher',
  description: 'SHSU SHPE convention resume preparation',
  applicationName: 'SHPE Resume Matcher',
  keywords: ['resume', 'matcher', 'job', 'application'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-US" className="h-full" suppressHydrationWarning>
      <body
        className={`${geist.variable} ${spaceGrotesk.variable} ${notoSansSC.variable} ${notoSansKR.variable} ${notoSansJP.variable} antialiased bg-background text-ink-soft min-h-full`}
      >
        {children}
      </body>
    </html>
  );
}
