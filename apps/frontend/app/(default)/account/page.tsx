'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api/client';

type Me = { email: string; is_admin: boolean };
type Usage = {
  allowance_cents: number;
  note: string;
  members: { owner_id: string; accounted_cents: number }[];
};

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteToken, setInviteToken] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => {
    apiFetch('/auth/me')
      .then((r) => r.json())
      .then(setMe);
  }, []);
  useEffect(() => {
    if (me?.is_admin)
      apiFetch('/auth/admin/usage')
        .then((r) => r.json())
        .then(setUsage);
  }, [me]);
  async function createInvite(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch('/auth/invitations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: inviteEmail }),
    });
    const body = await response.json();
    if (!response.ok) {
      setMessage(body.detail ?? 'Invitation failed');
      return;
    }
    setInviteToken(body.invitation_token);
    setMessage('Copy this token now; it is shown once.');
  }
  async function signOut() {
    await apiFetch('/auth/logout', { method: 'POST' });
    sessionStorage.removeItem('shpe_csrf');
    router.replace('/login');
  }
  return (
    <section className="mx-auto my-20 w-[min(92%,900px)] border border-black bg-background p-6 shadow-sw-xl md:p-10">
      <p className="font-mono text-xs font-bold uppercase text-blue-700">
        SHSU SHPE · Powered by Valiqen
      </p>
      <h1 className="mt-3 font-mono text-4xl font-bold uppercase">Account</h1>
      <p className="mt-5 font-mono text-sm">{me?.email ?? 'Loading…'}</p>
      <button
        onClick={signOut}
        className="mt-5 border border-black px-4 py-2 font-mono text-xs font-bold uppercase shadow-sw-sm"
      >
        Sign out
      </button>
      {me?.is_admin && (
        <div className="mt-10 border-t border-black pt-8">
          <h2 className="font-mono text-2xl font-bold uppercase">Pilot administration</h2>
          <p className="mt-2 text-sm">
            Invitation and aggregate usage only. Member resume contents are not available here.
          </p>
          <form onSubmit={createInvite} className="mt-6 flex flex-col gap-3 md:flex-row">
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="member@example.org"
              className="flex-1 border border-black bg-white p-3"
            />
            <button className="border border-black bg-blue-700 px-5 py-3 font-mono text-xs font-bold uppercase text-white shadow-sw-sm">
              Create invitation
            </button>
          </form>
          {message && <p className="mt-3 font-mono text-xs">{message}</p>}
          {inviteToken && (
            <textarea
              readOnly
              aria-label="One-time invitation token"
              value={inviteToken}
              className="mt-3 h-24 w-full border border-black bg-white p-3 font-mono text-xs"
            />
          )}
          {usage && (
            <div className="mt-8">
              <h3 className="font-mono text-lg font-bold uppercase">Aggregate usage</h3>
              <p className="mt-2 text-sm">
                App allowance: ${(usage.allowance_cents / 100).toFixed(2)}. {usage.note}
              </p>
              <p className="mt-2 font-mono text-sm">
                Members represented: {usage.members.length} · Accounted: $
                {(
                  usage.members.reduce((sum, member) => sum + member.accounted_cents, 0) / 100
                ).toFixed(2)}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
