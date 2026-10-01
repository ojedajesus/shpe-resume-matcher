# SHPE team hosting on Vercel and Supabase

This configuration preserves the existing website and invite-only account flow.
Supabase Postgres stores accounts, sessions, invitations, AI allowances, resumes,
job descriptions, saved improvements, configuration, and short-lived print drafts.
The current app stores extracted resume content; it does not retain original upload
files. PDF and Word downloads are generated on demand, not placed in public buckets.

## Projects

The separate Supabase project `shpe-resume-matcher` has been created in the Valiqen
organization: https://supabase.com/dashboard/project/fnonnsccpfvequyowyhh . The quoted project cost is $0/month on the current Free plan; this
is not a promise that future upgrades, usage or AI calls are free.
Do not reuse or modify RI-GOOD's project.

Create two Vercel projects in `ojeda04jesus-4632s-projects`, both connected to
`ojedajesus/shpe-resume-matcher` and the tested working branch:

| Project | Root directory | Framework |
| --- | --- | --- |
| `shpe-resume-matcher` | `apps/frontend` | Next.js |
| `shpe-resume-matcher-api` | `apps/backend` | FastAPI |

The frontend proxies `/api/*` to the backend so member session cookies stay on
one origin. Server-rendered print pages also use `BACKEND_ORIGIN`.

## Supabase schema

The migration `supabase/migrations/20261001062237_shpe_cloud_schema.sql` has been
applied to the new project and verified: 13 tables, all with RLS, zero grants to
`anon` or `authenticated`.
It creates 13 tables, enables RLS on all of them, and revokes browser/Data API
access. Authentication remains the application's existing invite/session system;
this is not a conversion to Supabase Auth. Backend queries enforce member ownership.
No Supabase service key is needed by the browser.

Use the project's transaction-pooler connection string (port 6543) for
`DATABASE_URL`. Obtain it from the new project's Connect panel, including its
password, and enter it into backend server environment variables. Never put it in
`NEXT_PUBLIC_*`, source control, terminal output, or a chat message.
SQLAlchemy uses psycopg, TLS, no prepared statements, and no client-side pooled
connections. Short write transactions use a transaction-scoped advisory lock to
preserve existing quota and confirmation concurrency semantics across workers.
Synchronous auth/quota writes and async document writes use separate locks to avoid
blocking an event loop behind its own async transaction.
Runtime requests do not create or alter Postgres tables.

## Backend environment

Configure Preview and Production separately; previews must not point at a client's
database. The first SHPE launch starts with an empty, dedicated database. Existing
local resumes and accounts are not deleted or automatically copied.

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Supabase transaction-pooler URL; secret |
| `ENCRYPTION_KEY` | One stable Fernet key; secret |
| `FRONTEND_BASE_URL` | Exact frontend deployment origin |
| `PDF_RENDERER_URL` | That frontend origin plus `/internal/pdf` |
| `PDF_RENDERER_SECRET` | A random 32-byte-or-longer shared secret |
| `AUTH_REQUIRED` | `true` |
| `COOKIE_SECURE` | `true` |
| `LLM_PROVIDER` | `anthropic` |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` |
| `LLM_API_KEY` | Owner's provider key; secret |
| `LITELLM_LOCAL_MODEL_COST_MAP` | `true` |
| `REQUEST_TIMEOUT_SECONDS` | `240` |

`DATA_DIR` uses `/tmp/shpe-resume-matcher` on Vercel for transient local work only.
Durable data and configuration use Postgres. Cloud startup refuses temporary SQLite
and a missing encryption key or PDF renderer configuration.
Keep `ENCRYPTION_KEY` stable: changing it invalidates encrypted provider keys and
short-lived print tokens. Generate it using `Fernet.generate_key()` and transfer
it securely into the backend environment. Do not print it in shared logs.

The backend Vercel configuration excludes the unused Playwright Node driver to
reduce the cloud bundle. All cloud PDF/page-fit work is routed to the frontend
renderer; local installs retain their normal Playwright renderer.
Check the actual Vercel bundle size and function duration against the account's
plan during deployment. Local site-packages size is not a deployed bundle size.

## Frontend environment

| Variable | Value |
| --- | --- |
| `BACKEND_ORIGIN` | Exact backend deployment origin |
| `NEXT_PUBLIC_API_URL` | `/` |
| `NEXT_PUBLIC_REQUEST_TIMEOUT_MS` | `240000` |
| `PDF_RENDER_ORIGIN` | Exact frontend deployment origin |
| `PDF_RENDERER_SECRET` | Same secret as backend; server-only |

`/internal/pdf` uses an HMAC signature and a timestamp, restricts requests to the
paired frontend's print routes, and requires scoped backend-issued render tokens.
It packages Chromium for serverless PDF generation; Word stays native editable
text. No external browser service is required.

If testing a Vercel-protected preview, the frontend renderer can use its
`VERCEL_AUTOMATION_BYPASS_SECRET`, and the backend can use
`FRONTEND_PROTECTION_BYPASS_SECRET` for requests to that protected frontend.
A Vercel-protected backend must also be reachable by the frontend. Do not confuse
Vercel deployment protection with the app's member login. For the approved team
launch, make the deployment URL accessible to members while keeping app
`AUTH_REQUIRED=true` and confirming unauthenticated API requests return 401.

## First owner and invitations

After the schema and backend environment are set, run the existing owner bootstrap
against the new database from a trusted terminal:

```powershell
cd C:\Users\ojeda\shpe-resume-matcher\apps\backend
uv run python -m app.scripts.bootstrap_owner YOUR_EMAIL
```

The terminal must have the new project's `DATABASE_URL` and `ENCRYPTION_KEY`
configured privately. The password is prompted twice, not committed or logged.
The bootstrap refuses to run if an account already exists. Sign in and use the
existing administration invitation flow for each team member. Do not share one
owner login with the team.

## Launch verification

Before sharing the link, verify:

1. Unauthorized API requests return 401 and member A cannot read member B's resume.
2. Owner login and an invitation acceptance work on the shared frontend origin.
3. Resume upload/parse and matching succeed with bounded owner-approved AI usage.
4. The chosen template appears in PDF and editable Word downloads.
5. Page fitting can read a draft handled by a different backend worker.
6. Saved data, sessions and settings survive redeployment.
7. No database password, provider key, encryption key or shared renderer secret is
   present in browser bundles or build logs.

A prepared repository is not a live deployment. Record the actual Vercel build,
Supabase migration checks and online flow results before calling the launch ready.

## Current verification and pending deployment

- 155 targeted backend tests passed on Python 3.13.15.
- 676 frontend tests passed; type checking and linting passed.
- Packaged Chromium 153 generated a synthetic PDF locally.
- Supabase migration and permissions were verified on the new Postgres project.
- Security advisors report only informational notices for RLS with no policies:
  intentional here because all browser table grants are revoked. See
  https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy .
- Performance advisors report unused indexes on the new empty database; retain
  indexes used by owner filtering and preview lookups.
- The local production build encountered Google font download failures. This is
  an unresolved environment/network verification limit; a successful Vercel build
  and an online PDF check are still required.
- No Vercel deployment has been completed. Specific deployment approval and secure
  database/provider environment provisioning are still pending.
