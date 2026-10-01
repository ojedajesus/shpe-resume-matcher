'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function AcceptInvitationPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    // Fragment values stay out of HTTP requests and referrer headers.
    const invitation = new URLSearchParams(window.location.hash.slice(1));
    if (invitation.has('token')) {
      setToken(invitation.get('token') || '');
      setEmail(invitation.get('email') || '');
      window.history.replaceState(null, '', window.location.pathname);
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setError('');
    if (password !== confirmation) {
      setError('Your passwords must match.');
      return;
    }
    setPending(true);
    try {
      const response = await fetch('/api/v1/auth/accept-invitation', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, invitation_token: token }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : 'Check your email, invitation, and password and try again.'
        );
        return;
      }
      sessionStorage.setItem('shpe_csrf', data.csrf_token);
      setPassword('');
      setConfirmation('');
      setToken('');
      router.replace('/dashboard');
    } catch {
      setError('Could not connect. Please try again.');
    } finally {
      setPending(false);
    }
  }

  const inputClass = 'border border-black bg-white p-3 text-base normal-case';
  return (
    <main
      className="min-h-screen bg-background p-4 md:p-12 lg:p-24"
      style={{
        backgroundImage:
          'linear-gradient(rgba(29,78,216,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(29,78,216,.1) 1px,transparent 1px)',
        backgroundSize: '40px 40px',
      }}
    >
      <section className="mx-auto max-w-3xl border border-black bg-background p-8 shadow-sw-xl md:p-16">
        <p className="font-mono text-sm font-bold uppercase text-blue-700">
          SHSU SHPE · Powered by Valiqen
        </p>
        <h1 className="mt-4 font-mono text-4xl font-bold uppercase tracking-tighter md:text-6xl">
          Accept invitation
        </h1>
        <p className="mt-6 font-mono text-sm">
          Create your private account using the email and one-time invitation from your chapter owner.
        </p>
        <form onSubmit={submit} className="mt-8 grid gap-5">
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            Email
            <input className={inputClass} type="email" autoComplete="email" required
              value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            Invitation token
            <input className={inputClass} type="password" autoComplete="off" required
              minLength={32} maxLength={256} value={token}
              onChange={(event) => setToken(event.target.value)} />
          </label>
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            New password (at least 12 characters)
            <input className={inputClass} type="password" autoComplete="new-password" required
              minLength={12} maxLength={256} value={password}
              onChange={(event) => setPassword(event.target.value)} />
          </label>
          <label className="grid gap-2 font-mono text-xs font-bold uppercase">
            Confirm password
            <input className={inputClass} type="password" autoComplete="new-password" required
              minLength={12} maxLength={256} value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)} />
          </label>
          {error && <p role="alert" className="border border-red-700 bg-red-50 p-3 font-mono text-sm text-red-800">{error}</p>}
          <button disabled={pending}
            className="border border-black bg-blue-700 p-3 font-mono text-sm font-bold uppercase text-white shadow-sw-default disabled:opacity-60">
            {pending ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="mt-8 font-mono text-xs">
          Already have an account? <Link href="/login" className="underline">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
