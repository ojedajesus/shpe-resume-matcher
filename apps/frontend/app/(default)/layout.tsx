import { ResumePreviewProvider } from '@/components/common/resume_previewer_context';
import { StatusCacheProvider } from '@/lib/context/status-cache';
import { LanguageProvider } from '@/lib/context/language-context';
import { LocalizedErrorBoundary } from '@/components/common/error-boundary';
import { AuthGate } from '@/components/auth/auth-gate';
import Link from 'next/link';

export default function DefaultLayout({ children }: { children: React.ReactNode }) {
  return (
    <StatusCacheProvider>
      <LanguageProvider>
        <ResumePreviewProvider>
          <LocalizedErrorBoundary>
            <AuthGate>
              <main className="min-h-screen flex flex-col">
                <Link
                  href="/account"
                  className="fixed right-4 top-4 z-40 border border-black bg-background px-3 py-2 font-mono text-xs font-bold uppercase text-blue-700 shadow-sw-sm"
                >
                  Account
                </Link>
                {children}
              </main>
            </AuthGate>
          </LocalizedErrorBoundary>
        </ResumePreviewProvider>
      </LanguageProvider>
    </StatusCacheProvider>
  );
}
