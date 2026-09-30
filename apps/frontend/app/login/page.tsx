'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      setError(data.detail ?? 'Sign in failed');
      return;
    }
    sessionStorage.setItem('shpe_csrf', data.csrf_token);
    router.replace(new URLSearchParams(window.location.search).get('next') || '/dashboard');
  }
  return (
    <main
      className="min-h-screen bg-background p-4 md:p-12 lg:p-24"
      style={{
        backgroundImage:
          'linear-gradient(rgba(29,78,216,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(29,78,216,.1) 1px,transparent 1px)',
        backgroundSize: '40px 40px',
      }}
    >
      <section className="mx-auto flex min-h-[70vh] max-w-3xl flex-col justify-center border border-black bg-background p-8 shadow-sw-xl md:p-16">
        <p className="font-mono text-sm font-bold uppercase text-blue-700">
          SHSU SHPE · Powered by Valiqen
        </p>
        <h1 className="mt-4 font-mono text-5xl font-bold uppercase tracking-tighter md:text-7xl">
          SHPE Resume Matcher
        </h1>
        <p className="mt-6 max-w-xl font-mono text-sm">
          Private, invitation-only resume preparation for convention members.
        </p>
        <form onSubmit={submit} className="mt-10 grid gap-5">
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            Email
            <input
              className="border border-black bg-white p-3 text-base normal-case"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            Password
            <input
              className="border border-black bg-white p-3 text-base normal-case"
              type="password"
              autoComplete="current-password"
              minLength={12}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p
              role="alert"
              className="border border-red-700 bg-red-50 p-3 font-mono text-sm text-red-800"
            >
              {error}
            </p>
          )}
          <button className="border border-black bg-blue-700 p-3 font-mono text-sm font-bold uppercase text-white shadow-sw-default hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none">
            Sign in
          </button>
        </form>
        <p className="mt-8 font-mono text-xs">
          Need access? Ask the chapter owner for a one-time invitation. There is no open signup.
        </p>
      </section>
    </main>
  );
}
