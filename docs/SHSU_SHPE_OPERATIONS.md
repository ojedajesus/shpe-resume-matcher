# SHSU SHPE pilot operations

This fork keeps Resume Matcher's Python, Next.js, editor, cover-letter,
interview-prep, and Chromium PDF-template architecture. It is an invite-only
pilot for nine members—not a job board or an employer ATS.

## Local setup

1. Install Python 3.13+, Node 20+, `uv`, and Chromium system libraries.
2. `cd apps/backend && uv sync && uv run playwright install chromium`
3. Copy `.env.example` to `.env`. Set `ANTHROPIC_API_KEY` only in the process
   secret store, `LLM_PROVIDER=anthropic`,
   `LLM_MODEL=claude-haiku-4-5-20251001`, `COOKIE_SECURE=true`, and the public
   `FRONTEND_BASE_URL`. Never place a key in Git or in a browser variable.
4. Create the first and only initial owner interactively:
   `uv run python -m app.scripts.bootstrap_owner owner@example.org`. There is
   no default password and bootstrap refuses once any account exists.
5. `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.
6. `cd ../frontend && npm ci && BACKEND_ORIGIN=http://127.0.0.1:8000 npm run build && npm start`.

The owner calls `POST /api/v1/auth/invitations` with an email and manually
delivers the returned one-time token. No outbound email service is required.
The recipient submits it once to `/api/v1/auth/accept-invitation` with their
email and new 12+ character password. Invitations expire within seven days.

## AI limits and honest interpretation

The default app allowance is **$40.00**, leaving an intended $10 reserve from
the owner's stated $50 Console funding. This is an application ledger, **not a
live Claude Console balance**; it cannot see unrelated applications' spend.
Each call atomically reserves a conservative four-attempt worst case before
network I/O: four transport attempts
(the initial request plus the configured three retries) using one token per
UTF-8 byte plus framing overhead, and reserves content-quality retries
separately. Provider token usage settles successful calls without refunding
possibly billed earlier attempts; uncertain failures
retain the reservation. Configure rates with
`ANTHROPIC_INPUT_MICROS_PER_TOKEN` and
`ANTHROPIC_OUTPUT_MICROS_PER_TOKEN` when Anthropic pricing changes.
For `claude-haiku-4-5-20251001`, startup accounting accepts only the reviewed
$1/million input and $5/million output rates; a mismatch disables calls rather
than risking an understated reservation.

All scores must be described as an **estimated job-description match**, never
an official ATS score or hiring guarantee. AI text is a draft: requirements
must be split into required/preferred and evidence into supported/needs detail/
not evidenced. The application prompts treat resumes and job descriptions as
quoted, untrusted data and prohibit invented experience, dates, skills,
credentials, achievements, and metrics. Missing facts become member questions.
Without `ANTHROPIC_API_KEY`, AI actions return unavailable; do not substitute
sample or fake output.

## Hosting, durability, and backups

Use one persistent container/VM service capable of Python subprocesses and
Chromium (for example, a Docker-capable Render/Fly/Railway service or a small
VM) plus the bundled Next.js standalone server. **Vercel frontend hosting alone
does not host the Python + Chromium application.** `docker-compose.yml` is the
deployment-ready baseline; set secrets and mount `apps/backend/data` on a
persistent encrypted volume. Do not run multiple backend workers with SQLite.

Back up `resume_matcher.db` using SQLite's online backup command and encrypt
the result; also back up the deployment secret configuration. Test restoration
quarterly. Uploaded source files, generated exports, database, and backups may
contain sensitive member data: restrict operator access, define retention, and
honor member deletion. Officers see invitations and aggregate usage only—not
resume content.

## Release checklist / limitations

- Supply the real API key only at deployment and validate with a synthetic
  resume; this repository uses mocks and does not prove live Claude behavior.
- Create and manually deliver the eight member invitations after owner setup.
- Terminate TLS at the host; secure cookies intentionally fail over plain HTTP
  unless `COOKIE_SECURE=false` is explicitly used for local development.
- Back up and restore the persistent volume before admitting real member data.
- Run backend, frontend, parser, PDF, quota-concurrency, cross-user isolation,
  and browser smoke tests. Never use student resumes or contact details.

### Verification handoff

The application deliberately retains upstream `next/font/google` mappings for
genuine Space Grotesk (Latin, including Spanish diacritics), Geist (Latin), and
the regional Noto Sans SC/KR/JP variable families. An offline build must fail
rather than substitute one family for another. Run the remaining checks on a
host that can reach PyPI and Google Fonts and has Chromium system libraries:

```bash
cd apps/backend
uv sync
uv run pytest tests/integration/test_pilot_auth.py \
  tests/integration/test_pilot_quota.py tests/unit/test_render_auth.py
uv run pytest
uv run playwright install chromium

cd ../frontend
npm ci
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Then start both servers with provider mocks, run the synthetic upload → job
comparison → grounded suggestions → editor → resume/cover-letter export browser
flow, inspect PDF text and page geometry, and capture desktop/mobile before and
after screenshots. Backend, browser, and real Chromium verification remain
unexecuted until those prerequisites are present; do not infer them from
compilation or focused frontend tests.
