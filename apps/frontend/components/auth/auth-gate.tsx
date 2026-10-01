'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [aiUnavailable, setAiUnavailable] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    if (pathname === '/') {
      setReady(true);
      return;
    }
    fetch('/api/v1/auth/me', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        const data = (await response.json()) as { csrf_token: string };
        sessionStorage.setItem('shpe_csrf', data.csrf_token);
        fetch('/api/v1/status', { credentials: 'include' })
          .then((status) => status.json())
          .then((status: { llm_configured?: boolean }) => setAiUnavailable(!status.llm_configured))
          .catch(() => setAiUnavailable(true));
        setReady(true);
      })
      .catch(() => router.replace('/login'));
  }, [pathname, router]);
  if (!ready)
    return (
      <main className="min-h-screen grid place-items-center bg-background font-mono uppercase">
        Checking session…
      </main>
    );
  return (
    <>
      {aiUnavailable && (
        <div className="border-b border-black bg-yellow-100 px-4 py-2 text-center font-mono text-xs font-bold uppercase">
          AI preparation is unavailable until the owner configures the server key. No sample output
          will be substituted.
        </div>
      )}
      {children}
    </>
  );
}
