'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function JoinPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await fetch('/api/v1/auth/accept-invitation', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        invitation_token: new URLSearchParams(window.location.search).get('token') ?? '',
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      setError(body.detail ?? 'Invitation could not be accepted');
      return;
    }
    sessionStorage.setItem('shpe_csrf', body.csrf_token);
    router.replace('/dashboard');
  }
  return (
    <main className="min-h-screen bg-background p-4 md:p-16">
      <section className="mx-auto mt-16 max-w-2xl border border-black bg-background p-8 shadow-sw-xl">
        <p className="font-mono text-xs font-bold uppercase text-blue-700">
          SHSU SHPE · Powered by Valiqen
        </p>
        <h1 className="mt-3 font-mono text-4xl font-bold uppercase">Accept invitation</h1>
        <form onSubmit={submit} className="mt-8 grid gap-4">
          <input
            aria-label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="border border-black p-3"
          />
          <input
            aria-label="New password"
            type="password"
            minLength={12}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="border border-black p-3"
          />
          <button className="border border-black bg-blue-700 p-3 font-mono text-xs font-bold uppercase text-white shadow-sw-sm">
            Create member account
          </button>
          {error && (
            <p role="alert" className="text-red-800">
              {error}
            </p>
          )}
        </form>
      </section>
    </main>
  );
}
