-- SHPE backend-only persistence. Existing invite/session authentication remains in the app.

-- No browser/Data API grants: all operations pass through owner-scoped backend methods.

BEGIN;

CREATE TABLE api_keys (
	provider VARCHAR NOT NULL, 
	ciphertext TEXT NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (provider)
);

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.api_keys FROM anon, authenticated;

CREATE TABLE applications (
	application_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	job_id VARCHAR NOT NULL, 
	resume_id VARCHAR NOT NULL, 
	master_resume_id VARCHAR, 
	status VARCHAR NOT NULL, 
	company VARCHAR, 
	role VARCHAR, 
	applied_at VARCHAR, 
	notes TEXT, 
	position INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (application_id), 
	CONSTRAINT uq_application_job_resume UNIQUE (job_id, resume_id)
);

CREATE INDEX ix_applications_job_id ON applications (job_id);

CREATE INDEX ix_applications_owner_id ON applications (owner_id);

CREATE INDEX ix_applications_resume_id ON applications (resume_id);

CREATE INDEX ix_applications_status ON applications (status);

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.applications FROM anon, authenticated;

CREATE TABLE auth_attempts (
	attempt_id VARCHAR NOT NULL, 
	subject_hash VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (attempt_id)
);

CREATE INDEX ix_auth_attempts_action ON auth_attempts (action);

CREATE INDEX ix_auth_attempts_created_at ON auth_attempts (created_at);

CREATE INDEX ix_auth_attempts_subject_hash ON auth_attempts (subject_hash);

ALTER TABLE public.auth_attempts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.auth_attempts FROM anon, authenticated;

CREATE TABLE cloud_config (
	config_id VARCHAR NOT NULL, 
	value JSON NOT NULL, 
	PRIMARY KEY (config_id)
);

ALTER TABLE public.cloud_config ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.cloud_config FROM anon, authenticated;

CREATE TABLE improvements (
	request_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	original_resume_id VARCHAR NOT NULL, 
	tailored_resume_id VARCHAR NOT NULL, 
	job_id VARCHAR NOT NULL, 
	improvements JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (request_id)
);

CREATE INDEX ix_improvements_owner_id ON improvements (owner_id);

CREATE INDEX ix_improvements_tailored_resume_id ON improvements (tailored_resume_id);

ALTER TABLE public.improvements ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.improvements FROM anon, authenticated;

CREATE TABLE invitations (
	token_hash VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	created_by VARCHAR NOT NULL, 
	used_at VARCHAR, 
	PRIMARY KEY (token_hash)
);

CREATE INDEX ix_invitations_email ON invitations (email);

ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.invitations FROM anon, authenticated;

CREATE TABLE jobs (
	job_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	resume_id VARCHAR, 
	created_at VARCHAR NOT NULL, 
	metadata_json JSON NOT NULL, 
	PRIMARY KEY (job_id)
);

CREATE INDEX ix_jobs_owner_id ON jobs (owner_id);

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.jobs FROM anon, authenticated;

CREATE TABLE render_drafts (
	token VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	value JSON NOT NULL, 
	PRIMARY KEY (token)
);

CREATE INDEX ix_render_drafts_expires_at ON render_drafts (expires_at);

CREATE INDEX ix_render_drafts_owner_id ON render_drafts (owner_id);

ALTER TABLE public.render_drafts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.render_drafts FROM anon, authenticated;

CREATE TABLE resumes (
	resume_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	content_type VARCHAR NOT NULL, 
	filename VARCHAR, 
	is_master BOOLEAN NOT NULL, 
	is_default_master BOOLEAN NOT NULL, 
	parent_id VARCHAR, 
	processed_data JSON, 
	processing_status VARCHAR NOT NULL, 
	processing_token VARCHAR, 
	cover_letter TEXT, 
	outreach_message TEXT, 
	interview_prep TEXT, 
	title VARCHAR, 
	original_markdown TEXT, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (resume_id)
);

CREATE INDEX ix_resumes_owner_id ON resumes (owner_id);

CREATE UNIQUE INDEX ux_resumes_single_default_master ON resumes (owner_id, is_default_master) WHERE is_default_master = true;

ALTER TABLE public.resumes ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.resumes FROM anon, authenticated;

CREATE TABLE sessions (
	token_hash VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	csrf_token VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	PRIMARY KEY (token_hash)
);

CREATE INDEX ix_sessions_expires_at ON sessions (expires_at);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.sessions FROM anon, authenticated;

CREATE TABLE tailoring_previews (
	improvements JSON, 
	source_data JSON, 
	preview_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	job_id VARCHAR NOT NULL, 
	payload_hash VARCHAR NOT NULL, 
	source_hash VARCHAR NOT NULL, 
	job_hash VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	result_resume_id VARCHAR, 
	claim_token VARCHAR, 
	claim_expires_at VARCHAR, 
	response_data JSON, 
	PRIMARY KEY (preview_id)
);

CREATE INDEX ix_preview_compatibility ON tailoring_previews (source_id, job_id, payload_hash, created_at);

CREATE INDEX ix_tailoring_previews_expires_at ON tailoring_previews (expires_at);

CREATE INDEX ix_tailoring_previews_job_id ON tailoring_previews (job_id);

CREATE INDEX ix_tailoring_previews_owner_id ON tailoring_previews (owner_id);

CREATE INDEX ix_tailoring_previews_result_resume_id ON tailoring_previews (result_resume_id);

CREATE INDEX ix_tailoring_previews_source_id ON tailoring_previews (source_id);

ALTER TABLE public.tailoring_previews ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.tailoring_previews FROM anon, authenticated;

CREATE TABLE usage_ledger (
	usage_id VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	operation VARCHAR NOT NULL, 
	reserved_cents INTEGER NOT NULL, 
	actual_cents INTEGER, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	status VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (usage_id)
);

CREATE INDEX ix_usage_ledger_owner_id ON usage_ledger (owner_id);

ALTER TABLE public.usage_ledger ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.usage_ledger FROM anon, authenticated;

CREATE TABLE users (
	user_id VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	password_hash TEXT NOT NULL, 
	is_admin BOOLEAN NOT NULL, 
	monthly_limit_cents INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (user_id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.users FROM anon, authenticated;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

COMMIT;
